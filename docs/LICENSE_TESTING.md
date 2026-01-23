# License Testing Guide

คู่มือการทดสอบระบบ License สำหรับ Revenue Intelligence System

## 📋 Table of Contents
- [Quick Start](#quick-start)
- [Generate Test Licenses](#generate-test-licenses)
- [Install License](#install-license)
- [Test Feature Restrictions](#test-feature-restrictions)
- [Troubleshooting](#troubleshooting)

---

## 🚀 Quick Start

### Prerequisites
- Docker running with containers up
- PyJWT and cryptography installed in Docker container

### Install Dependencies

```bash
# Start Docker
docker-compose up -d

# Install required Python packages
docker-compose exec web pip install PyJWT==2.8.0 cryptography==41.0.7
```

---

## 🔑 Generate Test Licenses

### Step 1: Run the Generator Script

```bash
docker-compose exec web python utils/generate_test_license.py
```

### Step 2: Check Generated Files

The script creates:
- `config/license_test_private.pem` - Private key (keep secret!)
- `config/license_test_public.pem` - Public key (distribute to customers)
- `config/test_licenses.json` - All test license tokens

### What Gets Generated

| Tier | Users | Records/Import | Validity | Use Case |
|------|-------|----------------|----------|----------|
| **Trial** | 2 | 1,000 | 30 days | Test basic features |
| **Basic** | 5 | 50,000 | 1 year | Test SMT + Reconciliation |
| **Professional** | 20 | 500,000 | 1 year | Test all features |
| **Enterprise** | ∞ | ∞ | Perpetual | Test unlimited mode |
| **Expiring Soon** | 20 | 500,000 | 15 days | Test expiry warning |
| **Expired** | 20 | 500,000 | -5 days | Test grace period |

---

## 📦 Install License

### Via Web UI (Recommended)

1. **Open License Page**
   ```
   http://localhost:5001/license
   ```

2. **Login as Admin**
   - Default admin credentials from your setup

3. **Click "Install / Update License"**
   - Click "Show Form" button

4. **Fill the Form**
   - **License Key**: Copy from `test_licenses.json` → `[tier].license_key`
   - **License Token (JWT)**: Copy from `test_licenses.json` → `[tier].license_token`
   - **Public Key (RSA)**: Copy from `test_licenses.json` → `[tier].public_key`

5. **Click "Install License"**
   - System will verify the token
   - If valid, license status will update immediately

### Via API (Advanced)

```bash
curl -X POST http://localhost:5001/api/settings/license \
  -H "Content-Type: application/json" \
  -H "X-CSRFToken: YOUR_CSRF_TOKEN" \
  -d '{
    "license_key": "NHSO-XXXXXXXX-YYYYYYYY",
    "license_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
    "public_key": "-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----"
  }'
```

---

## 🧪 Test Feature Restrictions

### Test 1: Import Limit (Trial vs Professional)

**Trial License (1,000 records limit):**
```bash
# Install trial license
# Try importing file with >1,000 records
docker-compose exec web python eclaim_import.py downloads/rep/large_file.xls

# Expected: ⚠️  Trial Mode: Limiting import to 1,000 records
```

**Professional License (500,000 records limit):**
```bash
# Install professional license
# Try importing same file
docker-compose exec web python eclaim_import.py downloads/rep/large_file.xls

# Expected: All records imported (up to 500,000)
```

### Test 2: SMT Budget Feature (Trial vs Basic)

**Trial License (SMT disabled):**
1. Install trial license
2. Go to Data Management → SMT Sync tab
3. Try to fetch SMT data
4. **Expected**: HTTP 403 error with message "SMT Budget feature requires Basic tier or higher license"

**Basic License (SMT enabled):**
1. Install basic license
2. Go to Data Management → SMT Sync tab
3. Fetch SMT data
4. **Expected**: Data fetched successfully

### Test 3: Reconciliation Feature (Trial vs Basic)

**Trial License (Reconciliation disabled):**
```bash
curl http://localhost:5001/api/analytics/reconciliation
# Expected: 403 Forbidden with upgrade message
```

**Basic License (Reconciliation enabled):**
```bash
curl http://localhost:5001/api/analytics/reconciliation
# Expected: 200 OK with reconciliation data
```

### Test 4: License Expiry Warning

**Expiring Soon License (15 days remaining):**
1. Install expiring_soon license
2. Check dashboard
3. **Expected**: Yellow warning banner "หมดอายุในอีก 15 วัน"

**Expired License (Grace Period):**
1. Install expired license
2. Check dashboard
3. **Expected**: Orange warning banner "ช่วงผ่อนผันเหลือ 2 วัน"

### Test 5: API Access Restriction

**Trial/Basic License (API disabled):**
```bash
# Try to access API endpoints (assuming API access check is implemented)
curl http://localhost:5001/api/external/claims
# Expected: 403 Forbidden
```

**Professional License (API enabled):**
```bash
curl http://localhost:5001/api/external/claims
# Expected: 200 OK with data
```

---

## 🔍 Verify License Status

### Check Current License

```bash
# Via API
curl http://localhost:5001/api/settings/license | jq

# Response shows:
# - is_valid: true/false
# - tier: trial/basic/professional/enterprise
# - status: active/expiring_soon/grace_period/invalid
# - days_until_expiry
# - features
```

### Check Logs

```bash
# Check startup logs
docker-compose logs web | grep -i license

# Expected on startup:
# ✓ Valid license - Tier: professional - Expires: 2025-12-31
# OR
# ⚠️  NO VALID LICENSE - RUNNING IN TRIAL MODE
```

---

## 🛠 Troubleshooting

### Issue: "Invalid license signature"

**Cause**: Public key doesn't match the private key used to sign

**Solution**:
```bash
# Regenerate licenses with matching keys
docker-compose exec web python utils/generate_test_license.py

# Use license_key, license_token, AND public_key from the SAME tier
```

### Issue: "License has expired"

**Cause**: JWT exp claim is in the past (beyond grace period)

**Solution**:
```bash
# Generate new license with future expiry
docker-compose exec web python utils/generate_test_license.py

# Or use the perpetual enterprise license
```

### Issue: "ModuleNotFoundError: No module named 'jwt'"

**Cause**: PyJWT not installed

**Solution**:
```bash
docker-compose exec web pip install PyJWT==2.8.0 cryptography==41.0.7

# Or rebuild Docker image
docker-compose build --no-cache web
docker-compose up -d
```

### Issue: Feature still accessible after installing Trial license

**Cause**: Old license cached or not properly verified

**Solution**:
```bash
# Remove old license
curl -X DELETE http://localhost:5001/api/settings/license

# Restart web container
docker-compose restart web

# Install new license
```

---

## 📝 Manual License Verification

You can manually verify a license token:

```python
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

# Load public key
with open('config/license_test_public.pem', 'r') as f:
    public_key_pem = f.read()

public_key = serialization.load_pem_public_key(
    public_key_pem.encode('utf-8'),
    backend=default_backend()
)

# Verify token
token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."
payload = jwt.decode(token, public_key, algorithms=['RS256'])

print("License Valid!")
print(f"Tier: {payload['tier']}")
print(f"Expires: {payload.get('exp')}")
```

---

## 🎯 Production License Generation

**For issuing real production licenses:**

1. **Generate Production Key Pair** (one-time)
   ```bash
   openssl genrsa -out license_private.pem 2048
   openssl rsa -in license_private.pem -pubout -out license_public.pem
   ```

2. **Keep Private Key Secure**
   - Store in secure vault (AWS Secrets Manager, HashiCorp Vault)
   - Never commit to git
   - Never share with customers

3. **Distribute to Customers**
   - Send: `license_key` + `license_token` + `public_key`
   - Private key stays with license issuer only

4. **Customer Installs**
   - Via `/license` page
   - Offline verification (no callback to license server)

---

## 📚 Additional Resources

- [License Management Guide](../docs/business/LICENSE_MANAGEMENT.md)
- [License Server Specification](../docs/business/LICENSE_SERVER_SPEC.md)
- [JWT.io Debugger](https://jwt.io) - Decode and verify JWT tokens online

---

**Last Updated**: 2026-01-17
