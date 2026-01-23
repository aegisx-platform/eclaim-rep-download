# License Management System

> ระบบจัดการ License สำหรับ Revenue Intelligence System

## Table of Contents

1. [License Model](#license-model)
2. [License Types](#license-types)
3. [License Generation](#license-generation)
4. [License Verification](#license-verification)
5. [Backend System](#backend-system)
6. [Implementation Guide](#implementation-guide)
7. [Security Considerations](#security-considerations)

---

## License Model

### แนวทางการออก License

**แนะนำ: Hybrid Model (Online + Offline)**
- ✅ **Online Activation** - ครั้งแรก (ตรวจสอบกับ License Server)
- ✅ **Offline Validation** - ใช้งานปกติ (ไม่ต้องต่อ internet)
- ✅ **Periodic Check** - ตรวจสอบ license ทุก 30 วัน (optional)

### License Parameters

```json
{
  "license_key": "NHSO-XXXXX-XXXXX-XXXXX-XXXXX",
  "hospital_code": "10670",
  "hospital_name": "โรงพยาบาลศิริราช",
  "tier": "professional",
  "features": ["download", "import", "analytics", "api"],
  "max_beds": 2300,
  "max_users": 10,
  "issued_date": "2026-01-17",
  "expiry_date": "2027-01-17",
  "support_level": "premium",
  "signature": "base64_encoded_signature"
}
```

---

## License Types

### 1. Perpetual License (ตลอดชีพ)
**Use Case:** โรงพยาบาลรัฐ, โครงการภาครัฐ

**ข้อดี:**
- ✅ จ่ายครั้งเดียว ใช้ตลอด
- ✅ ไม่ต้องต่ออายุ
- ✅ รองรับ air-gapped environment

**ข้อเสีย:**
- ⚠️ Support/Update แยกต่างหาก
- ⚠️ ราคาสูงกว่า subscription

**ราคาแนะนำ:**
```
- Starter: 150,000 บาท (1-50 เตียง)
- Professional: 350,000 บาท (51-300 เตียง)
- Enterprise: 800,000 บาท (300+ เตียง)
+ Support/Update: 15-20% ต่อปี
```

### 2. Subscription License (รายปี)
**Use Case:** โรงพยาบาลเอกชน, Medical Billing Companies

**ข้อดี:**
- ✅ ราคาต่ำกว่า perpetual
- ✅ รวม support + update ตลอดปี
- ✅ Cancel ได้เมื่อต้องการ

**ข้อเสีย:**
- ⚠️ ต้องต่ออายุทุกปี
- ⚠️ หมดอายุ = ใช้ไม่ได้

**ราคาแนะนำ:**
```
- Starter: 50,000 บาท/ปี
- Professional: 120,000 บาท/ปี
- Enterprise: 250,000 บาท/ปี
(รวม support + update)
```

### 3. Trial License (ทดลองใช้)
**Duration:** 30 วัน (full features)

**Purpose:**
- Demo สำหรับลูกค้า
- POC (Proof of Concept)
- Evaluation ก่อนตัดสินใจซื้อ

**Limitations:**
- ⏰ หมดอายุ 30 วัน
- 🔒 ต้อง activate online
- 📝 ต้องกรอกข้อมูลติดต่อ

---

## License Generation

### วิธีการออก License

#### แบบที่ 1: JWT-based License (แนะนำ)

**ข้อดี:**
- ✅ Stateless (ไม่ต้องเก็บ DB)
- ✅ Self-contained (มีข้อมูลครบใน token)
- ✅ Cryptographically signed
- ✅ Easy to validate offline

**โครงสร้าง:**
```python
import jwt
from datetime import datetime, timedelta

def generate_license(hospital_code, tier, days_valid=365):
    """
    Generate JWT-based license
    """
    secret_key = os.getenv('LICENSE_SECRET_KEY')  # Keep this SECRET!

    payload = {
        # License info
        'license_key': f'NHSO-{generate_key()}',
        'hospital_code': hospital_code,
        'tier': tier,
        'features': get_tier_features(tier),

        # Timing
        'iat': datetime.utcnow(),  # Issued at
        'exp': datetime.utcnow() + timedelta(days=days_valid),  # Expiry

        # Limits
        'max_users': get_tier_limit(tier, 'users'),
        'max_beds': get_tier_limit(tier, 'beds'),

        # Tracking
        'issuer': 'AegisX Platform',
        'version': '3.2.0'
    }

    # Sign with RS256 (asymmetric) for better security
    license_token = jwt.encode(
        payload,
        private_key,
        algorithm='RS256'
    )

    return license_token

def verify_license(license_token):
    """
    Verify license signature and expiry
    """
    try:
        payload = jwt.decode(
            license_token,
            public_key,
            algorithms=['RS256']
        )

        # Additional checks
        if payload['exp'] < datetime.utcnow().timestamp():
            return {'valid': False, 'reason': 'License expired'}

        return {'valid': True, 'data': payload}

    except jwt.ExpiredSignatureError:
        return {'valid': False, 'reason': 'License expired'}
    except jwt.InvalidSignatureError:
        return {'valid': False, 'reason': 'Invalid signature'}
    except Exception as e:
        return {'valid': False, 'reason': str(e)}
```

#### แบบที่ 2: Hardware-bound License (Floating License)

**ข้อดี:**
- ✅ ผูกกับเครื่อง (ป้องกันการ copy)
- ✅ รองรับ floating license (ใช้ได้หลายเครื่อง)

**วิธีการ:**
```python
import hashlib
import uuid

def get_machine_id():
    """
    Get unique machine identifier
    """
    # Method 1: MAC Address
    mac = uuid.getnode()

    # Method 2: Disk UUID (Linux)
    # disk_uuid = subprocess.check_output(['blkid', '-s', 'UUID', '-o', 'value', '/dev/sda1'])

    # Method 3: Docker container ID (if in container)
    # container_id = subprocess.check_output(['cat', '/proc/self/cgroup']).decode()

    return hashlib.sha256(str(mac).encode()).hexdigest()

def generate_license_with_machine_binding(hospital_code, machine_id, tier):
    """
    Generate license bound to specific machine
    """
    payload = {
        'hospital_code': hospital_code,
        'machine_id': machine_id,
        'tier': tier,
        # ... other fields
    }

    # Include machine_id in signature
    license_token = jwt.encode(payload, private_key, algorithm='RS256')

    return license_token

def verify_license_with_machine(license_token):
    """
    Verify license matches current machine
    """
    payload = jwt.decode(license_token, public_key, algorithms=['RS256'])

    current_machine_id = get_machine_id()

    if payload['machine_id'] != current_machine_id:
        return {'valid': False, 'reason': 'License not valid for this machine'}

    return {'valid': True, 'data': payload}
```

---

## License Verification

### Client-Side Verification Flow

```python
# utils/license_manager.py

import jwt
import os
from datetime import datetime
from pathlib import Path

class LicenseManager:
    def __init__(self):
        self.license_file = Path('config/license.key')
        self.public_key = self._load_public_key()

    def _load_public_key(self):
        """Load public key for verification"""
        public_key_file = Path('config/license_public.pem')
        if public_key_file.exists():
            return public_key_file.read_text()
        return None

    def load_license(self):
        """Load license from file"""
        if not self.license_file.exists():
            return None

        return self.license_file.read_text().strip()

    def verify_license(self, license_token=None):
        """
        Verify license validity

        Returns:
            dict: {
                'valid': bool,
                'tier': str,
                'features': list,
                'days_remaining': int,
                'reason': str (if invalid)
            }
        """
        if license_token is None:
            license_token = self.load_license()

        if not license_token:
            return {
                'valid': False,
                'reason': 'No license found',
                'action': 'Please activate license at /setup'
            }

        try:
            # Decode JWT
            payload = jwt.decode(
                license_token,
                self.public_key,
                algorithms=['RS256']
            )

            # Check expiry
            exp_timestamp = payload.get('exp')
            if exp_timestamp:
                exp_date = datetime.fromtimestamp(exp_timestamp)
                now = datetime.utcnow()

                if now > exp_date:
                    return {
                        'valid': False,
                        'reason': 'License expired',
                        'expired_date': exp_date.isoformat(),
                        'action': 'Please renew license'
                    }

                days_remaining = (exp_date - now).days
            else:
                # Perpetual license
                days_remaining = None

            # Check tier limits
            tier_limits = {
                'starter': {'max_users': 5, 'max_beds': 50},
                'professional': {'max_users': 10, 'max_beds': 300},
                'enterprise': {'max_users': 999, 'max_beds': 9999}
            }

            tier = payload.get('tier', 'starter')
            limits = tier_limits.get(tier, tier_limits['starter'])

            return {
                'valid': True,
                'tier': tier,
                'features': payload.get('features', []),
                'limits': limits,
                'hospital_code': payload.get('hospital_code'),
                'days_remaining': days_remaining,
                'expiry_date': exp_date.isoformat() if exp_timestamp else None
            }

        except jwt.ExpiredSignatureError:
            return {'valid': False, 'reason': 'License expired'}
        except jwt.InvalidSignatureError:
            return {'valid': False, 'reason': 'Invalid license signature'}
        except Exception as e:
            return {'valid': False, 'reason': f'License error: {str(e)}'}

    def save_license(self, license_token):
        """Save license to file"""
        self.license_file.parent.mkdir(parents=True, exist_ok=True)
        self.license_file.write_text(license_token)

    def get_license_info(self):
        """Get human-readable license info"""
        result = self.verify_license()

        if not result['valid']:
            return result

        info = {
            'status': '✅ Active' if result['valid'] else '❌ Invalid',
            'tier': result['tier'].title(),
            'features': result['features'],
            'limits': result['limits'],
            'hospital_code': result.get('hospital_code', 'N/A'),
        }

        if result.get('days_remaining'):
            if result['days_remaining'] <= 30:
                info['warning'] = f'⚠️ License expiring in {result["days_remaining"]} days'
            info['expires_in'] = f'{result["days_remaining"]} days'
        else:
            info['expires_in'] = 'Perpetual'

        return info

# Singleton instance
license_manager = LicenseManager()
```

### Integration with Flask App

```python
# app.py

from utils.license_manager import license_manager
from functools import wraps

def require_license(required_feature=None):
    """
    Decorator to require valid license for routes
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            result = license_manager.verify_license()

            if not result['valid']:
                return jsonify({
                    'success': False,
                    'error': 'License required',
                    'reason': result['reason'],
                    'action': result.get('action', 'Contact support')
                }), 403

            # Check feature access
            if required_feature:
                if required_feature not in result.get('features', []):
                    return jsonify({
                        'success': False,
                        'error': 'Feature not available in your license tier',
                        'required_feature': required_feature,
                        'current_tier': result['tier']
                    }), 403

            # Attach license info to request
            g.license_info = result

            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Usage examples
@app.route('/api/analytics/advanced')
@require_license(required_feature='advanced_analytics')
def advanced_analytics():
    # Only available for Professional/Enterprise tiers
    pass

@app.route('/api/downloads/bulk')
@require_license(required_feature='bulk_download')
def bulk_download():
    # Check concurrent user limit
    license_info = g.license_info
    active_users = get_active_user_count()

    if active_users >= license_info['limits']['max_users']:
        return jsonify({
            'success': False,
            'error': 'User limit reached',
            'limit': license_info['limits']['max_users']
        }), 403

    # Proceed with download
    pass

@app.route('/api/license/info')
def get_license_info():
    """Get current license information"""
    info = license_manager.get_license_info()
    return jsonify(info)

@app.route('/api/license/activate', methods=['POST'])
def activate_license():
    """Activate new license"""
    license_key = request.json.get('license_key')

    # Verify with license server (online activation)
    result = verify_with_license_server(license_key)

    if result['valid']:
        # Save license
        license_manager.save_license(result['license_token'])

        return jsonify({
            'success': True,
            'message': 'License activated successfully',
            'license_info': license_manager.get_license_info()
        })

    return jsonify({
        'success': False,
        'error': result.get('reason', 'Activation failed')
    }), 400
```

---

## Backend System

### ต้องมีระบบหลังบ้านไหม?

**คำตอบ: แนะนำให้มี (แต่ไม่จำเป็นต้องซับซ้อน)**

### License Server Architecture

```
┌─────────────────────────────────────────────┐
│         License Management System           │
│         (license.aegisx.com)               │
└─────────────────────────────────────────────┘
                    │
        ┌───────────┼───────────┐
        │           │           │
    ┌───▼───┐  ┌───▼────┐  ┌──▼──────┐
    │ Issue │  │Activate│  │ Verify  │
    │License│  │License │  │ License │
    └───────┘  └────────┘  └─────────┘
        │           │           │
    ┌───▼───────────▼───────────▼────┐
    │      PostgreSQL Database       │
    │  (licenses, activations, logs) │
    └────────────────────────────────┘
```

### Minimum Backend Requirements

**Option 1: Simple Flask API (แนะนำ)**

```python
# license_server/app.py

from flask import Flask, request, jsonify
import jwt
from datetime import datetime, timedelta
import secrets

app = Flask(__name__)

# Load private key (keep this VERY secure!)
PRIVATE_KEY = open('keys/license_private.pem').read()
PUBLIC_KEY = open('keys/license_public.pem').read()

@app.route('/api/license/issue', methods=['POST'])
@admin_required
def issue_license():
    """
    Issue new license (Admin only)

    POST /api/license/issue
    {
        "hospital_code": "10670",
        "hospital_name": "โรงพยาบาลศิริราช",
        "tier": "professional",
        "license_type": "subscription",  # or "perpetual"
        "days_valid": 365,
        "features": ["download", "import", "analytics"],
        "max_users": 10,
        "notes": "ลูกค้า tier Professional"
    }
    """
    data = request.json

    # Generate unique license key
    license_key = f"NHSO-{secrets.token_hex(4).upper()}-{secrets.token_hex(4).upper()}"

    # Create JWT payload
    payload = {
        'license_key': license_key,
        'hospital_code': data['hospital_code'],
        'hospital_name': data['hospital_name'],
        'tier': data['tier'],
        'features': data['features'],
        'max_users': data.get('max_users', 5),
        'iat': datetime.utcnow(),
        'iss': 'AegisX Platform',
    }

    # Add expiry for subscription licenses
    if data['license_type'] == 'subscription':
        payload['exp'] = datetime.utcnow() + timedelta(days=data['days_valid'])

    # Sign license
    license_token = jwt.encode(payload, PRIVATE_KEY, algorithm='RS256')

    # Save to database
    save_license_to_db({
        'license_key': license_key,
        'hospital_code': data['hospital_code'],
        'tier': data['tier'],
        'license_type': data['license_type'],
        'status': 'issued',
        'issued_at': datetime.utcnow(),
        'expires_at': payload.get('exp'),
        'license_token': license_token,
        'notes': data.get('notes', '')
    })

    return jsonify({
        'success': True,
        'license_key': license_key,
        'license_token': license_token,
        'public_key': PUBLIC_KEY,  # Send public key for verification
        'instructions': 'Save license_token to config/license.key'
    })

@app.route('/api/license/activate', methods=['POST'])
def activate_license():
    """
    Activate license (first-time activation)

    POST /api/license/activate
    {
        "license_key": "NHSO-XXXXX-XXXXX",
        "hospital_code": "10670",
        "machine_id": "sha256_hash_of_machine"
    }
    """
    data = request.json

    # Find license in database
    license_record = find_license_by_key(data['license_key'])

    if not license_record:
        return jsonify({
            'success': False,
            'error': 'Invalid license key'
        }), 404

    # Verify hospital code matches
    if license_record['hospital_code'] != data['hospital_code']:
        return jsonify({
            'success': False,
            'error': 'Hospital code does not match license'
        }), 403

    # Check if already activated
    activations = get_activations(data['license_key'])
    if len(activations) >= license_record.get('max_activations', 1):
        return jsonify({
            'success': False,
            'error': 'License activation limit reached'
        }), 403

    # Record activation
    save_activation({
        'license_key': data['license_key'],
        'machine_id': data.get('machine_id'),
        'activated_at': datetime.utcnow(),
        'ip_address': request.remote_addr
    })

    # Update license status
    update_license_status(data['license_key'], 'active')

    return jsonify({
        'success': True,
        'license_token': license_record['license_token'],
        'public_key': PUBLIC_KEY,
        'message': 'License activated successfully'
    })

@app.route('/api/license/verify', methods=['POST'])
def verify_license():
    """
    Verify license validity (optional periodic check)

    POST /api/license/verify
    {
        "license_token": "jwt_token_here"
    }
    """
    license_token = request.json.get('license_token')

    try:
        payload = jwt.decode(license_token, PUBLIC_KEY, algorithms=['RS256'])

        license_key = payload['license_key']

        # Check if license is revoked
        license_record = find_license_by_key(license_key)
        if license_record['status'] == 'revoked':
            return jsonify({
                'valid': False,
                'reason': 'License has been revoked'
            }), 403

        return jsonify({
            'valid': True,
            'data': payload
        })

    except jwt.ExpiredSignatureError:
        return jsonify({'valid': False, 'reason': 'License expired'}), 403
    except Exception as e:
        return jsonify({'valid': False, 'reason': str(e)}), 400

@app.route('/api/license/revoke', methods=['POST'])
@admin_required
def revoke_license():
    """
    Revoke license (Admin only)

    POST /api/license/revoke
    {
        "license_key": "NHSO-XXXXX-XXXXX",
        "reason": "Customer requested cancellation"
    }
    """
    data = request.json

    update_license_status(
        data['license_key'],
        'revoked',
        revoke_reason=data.get('reason', '')
    )

    return jsonify({
        'success': True,
        'message': 'License revoked'
    })
```

**Option 2: Serverless (AWS Lambda + DynamoDB)**

```yaml
# AWS SAM template
Resources:
  LicenseAPI:
    Type: AWS::Serverless::Function
    Properties:
      Handler: license_handler.lambda_handler
      Runtime: python3.12
      Environment:
        Variables:
          LICENSE_TABLE: !Ref LicenseTable
      Events:
        IssueAPI:
          Type: Api
          Properties:
            Path: /license/issue
            Method: POST
        ActivateAPI:
          Type: Api
          Properties:
            Path: /license/activate
            Method: POST

  LicenseTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: nhso-licenses
      AttributeDefinitions:
        - AttributeName: license_key
          AttributeType: S
      KeySchema:
        - AttributeName: license_key
          KeyType: HASH
```

### Database Schema (License Server)

```sql
-- licenses table
CREATE TABLE licenses (
    id SERIAL PRIMARY KEY,
    license_key VARCHAR(100) UNIQUE NOT NULL,
    hospital_code VARCHAR(10) NOT NULL,
    hospital_name VARCHAR(255),
    tier VARCHAR(50) NOT NULL,  -- starter, professional, enterprise
    license_type VARCHAR(50) NOT NULL,  -- perpetual, subscription, trial
    status VARCHAR(50) DEFAULT 'issued',  -- issued, active, expired, revoked

    -- License content
    license_token TEXT NOT NULL,
    features JSONB,  -- ["download", "import", "analytics", "api"]

    -- Limits
    max_users INTEGER DEFAULT 5,
    max_beds INTEGER DEFAULT 50,
    max_activations INTEGER DEFAULT 1,

    -- Timing
    issued_at TIMESTAMP DEFAULT NOW(),
    activated_at TIMESTAMP,
    expires_at TIMESTAMP,
    revoked_at TIMESTAMP,

    -- Tracking
    issued_by VARCHAR(100),
    revoke_reason TEXT,
    notes TEXT,

    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- activations table
CREATE TABLE license_activations (
    id SERIAL PRIMARY KEY,
    license_key VARCHAR(100) REFERENCES licenses(license_key),
    machine_id VARCHAR(255),
    ip_address INET,
    activated_at TIMESTAMP DEFAULT NOW(),
    last_seen_at TIMESTAMP,
    user_agent TEXT,

    UNIQUE(license_key, machine_id)
);

-- verification_logs table (optional - for analytics)
CREATE TABLE license_verification_logs (
    id SERIAL PRIMARY KEY,
    license_key VARCHAR(100),
    verified_at TIMESTAMP DEFAULT NOW(),
    ip_address INET,
    result VARCHAR(50),  -- valid, expired, revoked, invalid
    error_message TEXT
);

CREATE INDEX idx_licenses_hospital ON licenses(hospital_code);
CREATE INDEX idx_licenses_status ON licenses(status);
CREATE INDEX idx_activations_license ON license_activations(license_key);
```

---

## Implementation Guide

### Step-by-Step Implementation

#### Phase 1: License Generation (Backend)

**สิ่งที่ต้องทำ:**

1. **สร้าง RSA Key Pair**
```bash
# Generate private key (keep secret!)
openssl genrsa -out license_private.pem 2048

# Generate public key (distribute to clients)
openssl rsa -in license_private.pem -pubout -out license_public.pem
```

2. **สร้าง License Server (Flask/FastAPI)**
   - ติดตั้ง: `pip install flask pyjwt cryptography`
   - เขียน API endpoints (issue, activate, verify)
   - ตั้ง database (PostgreSQL/MySQL)

3. **สร้าง Admin Panel สำหรับออก License**
   - Form สร้าง license
   - ดู license ที่ออกไปแล้ว
   - Revoke license

#### Phase 2: License Verification (Client)

**สิ่งที่ต้องทำ:**

1. **เพิ่ม License Manager ใน Application**
```bash
# สร้างไฟล์
touch utils/license_manager.py
```

2. **เพิ่ม Public Key ใน Docker Image**
```dockerfile
# Dockerfile
COPY config/license_public.pem /app/config/
```

3. **เพิ่ม License Check ใน Startup**
```python
# docker-entrypoint.sh หรือ app.py
from utils.license_manager import license_manager

# Check license on startup
license_info = license_manager.verify_license()
if not license_info['valid']:
    print(f"⚠️  License issue: {license_info['reason']}")
    # Show warning but allow to continue to /setup page
```

4. **เพิ่ม License Activation UI**
   - เพิ่มในหน้า /setup
   - ฟอร์มกรอก license key
   - ปุ่ม activate (เชื่อมกับ license server)

#### Phase 3: Feature Gating

**ตัวอย่างการจำกัด Feature:**

```python
# app.py

@app.route('/api/analytics/benchmark')
@require_license(required_feature='benchmark')
def benchmark_analytics():
    """Benchmark feature - Enterprise only"""
    pass

@app.route('/api/downloads/parallel')
@require_license(required_feature='parallel_download')
def parallel_download():
    """Parallel download - Professional+ only"""
    pass

# Template: Show/hide features based on license
@app.context_processor
def inject_license():
    license_info = license_manager.get_license_info()
    return {'license_info': license_info}
```

```html
<!-- templates/dashboard.html -->
{% if 'advanced_analytics' in license_info.features %}
<div class="premium-feature">
    <h3>Advanced Analytics</h3>
    <!-- Show feature -->
</div>
{% else %}
<div class="upgrade-prompt">
    <h3>🔒 Advanced Analytics</h3>
    <p>Available in Professional and Enterprise tiers</p>
    <button onclick="showUpgradeDialog()">Upgrade</button>
</div>
{% endif %}
```

---

## Security Considerations

### ⚠️ Security Best Practices

1. **Private Key Security**
   - ❌ NEVER commit private key to git
   - ✅ Store in secure vault (AWS Secrets Manager, HashiCorp Vault)
   - ✅ Rotate keys periodically (every 1-2 years)

2. **License Tampering Prevention**
   - ✅ Use asymmetric encryption (RS256)
   - ✅ Include checksum in license
   - ✅ Obfuscate license validation code

3. **Activation Security**
   - ✅ Rate limit activation attempts
   - ✅ Log all activation attempts
   - ✅ Require machine binding for sensitive tiers

4. **Network Security**
   - ✅ Use HTTPS for license server
   - ✅ Implement API authentication (API keys)
   - ✅ Add IP whitelist for admin endpoints

### License Cracking Prevention

**ไม่มี license ที่ crack ไม่ได้ 100%** แต่ทำให้ยากที่สุด:

1. **Code Obfuscation**
```bash
pip install pyarmor
pyarmor obfuscate utils/license_manager.py
```

2. **Server-Side Validation** (Online check)
   - Periodic check ทุก 30 วัน
   - ถ้าไม่ผ่านแสดง warning แต่ยังใช้ได้ (grace period)

3. **License Binding**
   - Bind กับ hospital_code + machine_id
   - ป้องกันการ copy ไปใช้โรงพยาบาลอื่น

4. **Watermarking**
   - ใส่ hospital_code ใน exported reports
   - ติดตาม leak ได้

---

## Summary & Recommendations

### แนวทางที่แนะนำสำหรับ Revenue Intelligence System:

✅ **License Model:** Hybrid (Perpetual + Subscription)
- โรงพยาบาลรัฐ: Perpetual
- โรงพยาบาลเอกชน: Subscription

✅ **Verification:** JWT-based (Offline validation)
- ไม่ต้อง internet ตลอดเวลา
- Optional online check ทุก 30 วัน

✅ **Backend:** Simple Flask API + PostgreSQL
- ไม่ซับซ้อน, maintain ง่าย
- Deploy บน AWS/DigitalOcean

✅ **Tier Structure:**
```
Starter:       50,000/ปี หรือ 150,000 แบบตลอดชีพ
Professional: 120,000/ปี หรือ 350,000 แบบตลอดชีพ
Enterprise:   250,000/ปี หรือ 800,000 แบบตลอดชีพ
```

✅ **Features by Tier:**
```
Starter:      download, import, basic_analytics
Professional: + api, benchmark, advanced_analytics, bulk_download
Enterprise:   + multi_user, custom_reports, priority_support, sla
```

### Quick Start Checklist

- [ ] สร้าง RSA key pair
- [ ] สร้าง license server (Flask API)
- [ ] สร้าง database schema
- [ ] เพิ่ม `license_manager.py` ใน client
- [ ] เพิ่ม license activation UI ที่ /setup
- [ ] เพิ่ม feature gating ใน API
- [ ] Test license issuance & activation
- [ ] Deploy license server

---

**ต้องการความช่วยเหลือเพิ่มเติม?**
- Implementation guide: ดู `docs/technical/LICENSE_IMPLEMENTATION.md`
- API documentation: ดู license server API docs
- Contact: license@aegisx.com
