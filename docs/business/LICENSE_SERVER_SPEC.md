# License Server - Technical Specification

> Technology-Agnostic Specification for License Management System

**Version:** 1.0.0
**Last Updated:** 2026-01-17

---

## Table of Contents

1. [Overview](#overview)
2. [API Specification](#api-specification)
3. [Database Schema](#database-schema)
4. [License Token Format](#license-token-format)
5. [Authentication & Security](#authentication--security)
6. [Client Integration](#client-integration)
7. [Deployment Architecture](#deployment-architecture)
8. [Testing Requirements](#testing-requirements)

---

## Overview

### System Purpose

License Server ให้บริการ:
- ออก license สำหรับลูกค้า
- Activate license ครั้งแรก
- Verify license validity
- Manage license lifecycle (renew, revoke)
- Track usage & analytics

### Design Principles

- **Technology Agnostic** - Implement ได้ทั้ง Python (Flask/FastAPI) และ Node.js
- **RESTful API** - HTTP/JSON standard
- **Stateless** - ใช้ JWT (no server-side session)
- **Secure** - RSA signing, HTTPS only
- **Scalable** - Horizontal scaling support

---

## API Specification

### Base URL

```
Production:  https://license.aegisx.com/api/v1
Staging:     https://license-staging.aegisx.com/api/v1
Development: http://localhost:8000/api/v1
```

### Authentication

**Admin Endpoints:** Require API Key in header
```http
Authorization: Bearer {admin_api_key}
```

**Public Endpoints:** No auth required (rate limited)

---

### Endpoints

#### 1. Issue License (Admin)

**Purpose:** ออก license ใหม่สำหรับลูกค้า

```http
POST /licenses/issue
Authorization: Bearer {admin_api_key}
Content-Type: application/json
```

**Request Body:**
```json
{
  "hospital_code": "10670",
  "hospital_name": "โรงพยาบาลศิริราช",
  "tier": "professional",
  "license_type": "subscription",
  "days_valid": 365,
  "features": ["download", "import", "analytics", "api"],
  "limits": {
    "max_users": 10,
    "max_beds": 300
  },
  "notes": "ลูกค้า Professional tier",
  "issued_by": "admin@aegisx.com"
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "license_key": "NHSO-A1B2C3D4-E5F6G7H8",
    "license_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
    "public_key": "-----BEGIN PUBLIC KEY-----\n...",
    "issued_at": "2026-01-17T10:30:00Z",
    "expires_at": "2027-01-17T10:30:00Z"
  },
  "instructions": {
    "step_1": "Save license_token to config/license.key",
    "step_2": "Save public_key to config/license_public.pem",
    "step_3": "Restart application"
  }
}
```

**Error Responses:**
```json
// 400 Bad Request - Invalid input
{
  "success": false,
  "error": "validation_error",
  "message": "Invalid tier: must be starter, professional, or enterprise",
  "field": "tier"
}

// 401 Unauthorized - Invalid API key
{
  "success": false,
  "error": "unauthorized",
  "message": "Invalid or missing API key"
}

// 409 Conflict - Duplicate license
{
  "success": false,
  "error": "duplicate_license",
  "message": "Active license already exists for hospital_code 10670"
}
```

---

#### 2. Activate License (Public)

**Purpose:** Activate license ครั้งแรกบนเครื่องลูกค้า

```http
POST /licenses/activate
Content-Type: application/json
```

**Request Body:**
```json
{
  "license_key": "NHSO-A1B2C3D4-E5F6G7H8",
  "hospital_code": "10670",
  "machine_id": "abc123def456",
  "metadata": {
    "hostname": "hospital-server-01",
    "ip_address": "192.168.1.100",
    "os": "Ubuntu 22.04",
    "docker_version": "24.0.0"
  }
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "license_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
    "public_key": "-----BEGIN PUBLIC KEY-----\n...",
    "license_info": {
      "tier": "professional",
      "features": ["download", "import", "analytics", "api"],
      "limits": {
        "max_users": 10,
        "max_beds": 300
      },
      "expires_at": "2027-01-17T10:30:00Z"
    },
    "activation_id": "act_1234567890"
  }
}
```

**Error Responses:**
```json
// 404 Not Found - License not found
{
  "success": false,
  "error": "license_not_found",
  "message": "No license found with key NHSO-A1B2C3D4-E5F6G7H8"
}

// 403 Forbidden - Hospital code mismatch
{
  "success": false,
  "error": "hospital_mismatch",
  "message": "Hospital code does not match license"
}

// 409 Conflict - Already activated
{
  "success": false,
  "error": "activation_limit_reached",
  "message": "License activation limit reached (max: 1 activations)",
  "current_activations": 1,
  "max_activations": 1
}
```

---

#### 3. Verify License (Public)

**Purpose:** ตรวจสอบ license validity (periodic check)

```http
POST /licenses/verify
Content-Type: application/json
```

**Request Body:**
```json
{
  "license_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
  "machine_id": "abc123def456"
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "valid": true,
  "data": {
    "license_key": "NHSO-A1B2C3D4-E5F6G7H8",
    "tier": "professional",
    "status": "active",
    "expires_at": "2027-01-17T10:30:00Z",
    "days_remaining": 365
  }
}
```

**Error Responses:**
```json
// 403 Forbidden - Revoked license
{
  "success": true,
  "valid": false,
  "error": "license_revoked",
  "message": "License has been revoked",
  "revoked_at": "2026-06-15T14:20:00Z",
  "reason": "Customer requested cancellation"
}

// 403 Forbidden - Expired license
{
  "success": true,
  "valid": false,
  "error": "license_expired",
  "message": "License expired on 2026-12-31",
  "expired_at": "2026-12-31T23:59:59Z"
}
```

---

#### 4. Revoke License (Admin)

**Purpose:** ยกเลิก license

```http
POST /licenses/revoke
Authorization: Bearer {admin_api_key}
Content-Type: application/json
```

**Request Body:**
```json
{
  "license_key": "NHSO-A1B2C3D4-E5F6G7H8",
  "reason": "Customer requested cancellation",
  "revoked_by": "admin@aegisx.com"
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "license_key": "NHSO-A1B2C3D4-E5F6G7H8",
    "status": "revoked",
    "revoked_at": "2026-01-17T10:30:00Z"
  }
}
```

---

#### 5. Renew License (Admin)

**Purpose:** ต่ออายุ license

```http
POST /licenses/renew
Authorization: Bearer {admin_api_key}
Content-Type: application/json
```

**Request Body:**
```json
{
  "license_key": "NHSO-A1B2C3D4-E5F6G7H8",
  "days_extend": 365,
  "notes": "Renewed for 1 year"
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "license_key": "NHSO-A1B2C3D4-E5F6G7H8",
    "new_license_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
    "old_expires_at": "2026-01-17T10:30:00Z",
    "new_expires_at": "2027-01-17T10:30:00Z"
  }
}
```

---

#### 6. List Licenses (Admin)

**Purpose:** ดูรายการ license ทั้งหมด

```http
GET /licenses?page=1&limit=20&status=active&tier=professional
Authorization: Bearer {admin_api_key}
```

**Query Parameters:**
- `page` (int, default: 1) - Page number
- `limit` (int, default: 20, max: 100) - Items per page
- `status` (string) - Filter by status: `active`, `expired`, `revoked`
- `tier` (string) - Filter by tier: `starter`, `professional`, `enterprise`
- `search` (string) - Search by hospital_code or hospital_name

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "licenses": [
      {
        "license_key": "NHSO-A1B2C3D4-E5F6G7H8",
        "hospital_code": "10670",
        "hospital_name": "โรงพยาบาลศิริราช",
        "tier": "professional",
        "status": "active",
        "issued_at": "2026-01-17T10:30:00Z",
        "expires_at": "2027-01-17T10:30:00Z",
        "activations_count": 1
      }
    ],
    "pagination": {
      "page": 1,
      "limit": 20,
      "total": 156,
      "total_pages": 8
    }
  }
}
```

---

#### 7. Get License Details (Admin)

**Purpose:** ดูรายละเอียด license

```http
GET /licenses/{license_key}
Authorization: Bearer {admin_api_key}
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "license_key": "NHSO-A1B2C3D4-E5F6G7H8",
    "hospital_code": "10670",
    "hospital_name": "โรงพยาบาลศิริราช",
    "tier": "professional",
    "license_type": "subscription",
    "status": "active",
    "features": ["download", "import", "analytics", "api"],
    "limits": {
      "max_users": 10,
      "max_beds": 300
    },
    "issued_at": "2026-01-17T10:30:00Z",
    "expires_at": "2027-01-17T10:30:00Z",
    "issued_by": "admin@aegisx.com",
    "activations": [
      {
        "activation_id": "act_1234567890",
        "machine_id": "abc123def456",
        "activated_at": "2026-01-17T11:00:00Z",
        "last_seen_at": "2026-01-17T12:30:00Z",
        "metadata": {
          "hostname": "hospital-server-01",
          "ip_address": "192.168.1.100"
        }
      }
    ],
    "notes": "ลูกค้า Professional tier"
  }
}
```

---

#### 8. Health Check (Public)

**Purpose:** ตรวจสอบสถานะ server

```http
GET /health
```

**Response (200 OK):**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2026-01-17T10:30:00Z",
  "services": {
    "database": "connected",
    "cache": "connected"
  }
}
```

---

## Database Schema

### Technology-Agnostic Schema

**Database:** PostgreSQL หรือ MySQL

### Table: licenses

```sql
CREATE TABLE licenses (
    -- Primary key
    id VARCHAR(36) PRIMARY KEY,  -- UUID v4

    -- License identification
    license_key VARCHAR(100) UNIQUE NOT NULL,
    license_token TEXT NOT NULL,

    -- Customer info
    hospital_code VARCHAR(10) NOT NULL,
    hospital_name VARCHAR(255),

    -- License details
    tier VARCHAR(50) NOT NULL,  -- starter, professional, enterprise
    license_type VARCHAR(50) NOT NULL,  -- perpetual, subscription, trial
    status VARCHAR(50) DEFAULT 'issued',  -- issued, active, expired, revoked

    -- Features & limits (JSON)
    features JSON,  -- ["download", "import", "analytics"]
    limits JSON,    -- {"max_users": 10, "max_beds": 300}

    -- Activation control
    max_activations INTEGER DEFAULT 1,

    -- Timing
    issued_at TIMESTAMP NOT NULL,
    activated_at TIMESTAMP,
    expires_at TIMESTAMP,
    revoked_at TIMESTAMP,

    -- Tracking
    issued_by VARCHAR(100),
    revoked_by VARCHAR(100),
    revoke_reason TEXT,
    notes TEXT,

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_licenses_hospital_code ON licenses(hospital_code);
CREATE INDEX idx_licenses_status ON licenses(status);
CREATE INDEX idx_licenses_tier ON licenses(tier);
CREATE INDEX idx_licenses_expires_at ON licenses(expires_at);
```

### Table: license_activations

```sql
CREATE TABLE license_activations (
    -- Primary key
    id VARCHAR(36) PRIMARY KEY,  -- UUID v4

    -- Foreign key
    license_id VARCHAR(36) NOT NULL,
    license_key VARCHAR(100) NOT NULL,

    -- Machine binding
    machine_id VARCHAR(255),

    -- Metadata (JSON)
    metadata JSON,  -- {"hostname": "...", "ip": "...", "os": "..."}

    -- Tracking
    activated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP,
    ip_address VARCHAR(45),  -- IPv6 compatible
    user_agent TEXT,

    -- Constraints
    FOREIGN KEY (license_id) REFERENCES licenses(id) ON DELETE CASCADE,
    UNIQUE(license_key, machine_id)
);

-- Indexes
CREATE INDEX idx_activations_license_key ON license_activations(license_key);
CREATE INDEX idx_activations_machine_id ON license_activations(machine_id);
CREATE INDEX idx_activations_last_seen ON license_activations(last_seen_at);
```

### Table: verification_logs (Optional)

```sql
CREATE TABLE verification_logs (
    id VARCHAR(36) PRIMARY KEY,
    license_key VARCHAR(100),
    machine_id VARCHAR(255),
    result VARCHAR(50),  -- valid, expired, revoked, invalid
    error_message TEXT,
    verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ip_address VARCHAR(45)
);

-- Index for analytics
CREATE INDEX idx_logs_verified_at ON verification_logs(verified_at);
CREATE INDEX idx_logs_license_key ON verification_logs(license_key);
```

### Table: admin_audit_logs

```sql
CREATE TABLE admin_audit_logs (
    id VARCHAR(36) PRIMARY KEY,
    action VARCHAR(100) NOT NULL,  -- issue_license, revoke_license, renew_license
    admin_email VARCHAR(255) NOT NULL,
    license_key VARCHAR(100),
    details JSON,
    ip_address VARCHAR(45),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_admin ON admin_audit_logs(admin_email);
CREATE INDEX idx_audit_created ON admin_audit_logs(created_at);
```

---

## License Token Format

### JWT Structure

**Algorithm:** RS256 (RSA Signature with SHA-256)

**Header:**
```json
{
  "alg": "RS256",
  "typ": "JWT"
}
```

**Payload:**
```json
{
  // Standard JWT claims
  "iss": "AegisX Platform",          // Issuer
  "iat": 1705483800,                 // Issued at (Unix timestamp)
  "exp": 1737019800,                 // Expires at (Unix timestamp) - Only for subscription

  // License claims
  "license_key": "NHSO-A1B2C3D4-E5F6G7H8",
  "hospital_code": "10670",
  "hospital_name": "โรงพยาบาลศิริราช",
  "tier": "professional",
  "license_type": "subscription",

  // Features & limits
  "features": ["download", "import", "analytics", "api"],
  "limits": {
    "max_users": 10,
    "max_beds": 300
  },

  // Version
  "version": "1.0.0"
}
```

**Signature:**
```
RSASHA256(
  base64UrlEncode(header) + "." + base64UrlEncode(payload),
  private_key
)
```

### Token Example

```
eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJBZWdpc1ggUGxhdGZvcm0iLCJpYXQiOjE3MDU0ODM4MDAsImV4cCI6MTczNzAxOTgwMCwibGljZW5zZV9rZXkiOiJOSFNPLUExQjJDM0Q0LUU1RjZHN0g4IiwiaG9zcGl0YWxfY29kZSI6IjEwNjcwIiwiaG9zcGl0YWxfbmFtZSI6IuC5guC4o-C4h-C4nuC4ouC4suC4muC4suC4peC4qOC4tOC4o-C4tOC4o-C4suC4iCIsInRpZXIiOiJwcm9mZXNzaW9uYWwiLCJsaWNlbnNlX3R5cGUiOiJzdWJzY3JpcHRpb24iLCJmZWF0dXJlcyI6WyJkb3dubG9hZCIsImltcG9ydCIsImFuYWx5dGljcyIsImFwaSJdLCJsaW1pdHMiOnsibWF4X3VzZXJzIjoxMCwibWF4X2JlZHMiOjMwMH0sInZlcnNpb24iOiIxLjAuMCJ9.signature_here
```

### Perpetual License (No Expiry)

สำหรับ perpetual license - ไม่มี `exp` claim:

```json
{
  "iss": "AegisX Platform",
  "iat": 1705483800,
  // NO exp field for perpetual
  "license_key": "NHSO-A1B2C3D4-E5F6G7H8",
  "tier": "enterprise",
  "license_type": "perpetual",
  // ... rest of claims
}
```

---

## Authentication & Security

### Admin API Authentication

**Method:** Bearer Token (API Key)

```http
Authorization: Bearer sk_live_abc123def456ghi789
```

**API Key Format:**
```
sk_{env}_{random_32_chars}

Examples:
- sk_live_abc123def456ghi789jkl012  (Production)
- sk_test_xyz987wvu654tsr321opq210  (Testing)
```

**Storage:** Environment variable
```bash
ADMIN_API_KEY=sk_live_abc123def456ghi789jkl012
```

### Public Endpoint Rate Limiting

**Rate Limits:**
```
Activate: 5 requests/hour per IP
Verify:   100 requests/hour per IP
```

**Response Header:**
```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1705483800
```

**Rate Limit Exceeded (429):**
```json
{
  "success": false,
  "error": "rate_limit_exceeded",
  "message": "Too many requests. Please try again later.",
  "retry_after": 3600
}
```

### RSA Key Management

**Key Generation:**
```bash
# Private key (2048-bit RSA)
openssl genrsa -out license_private.pem 2048

# Public key
openssl rsa -in license_private.pem -pubout -out license_public.pem
```

**Key Rotation Strategy:**
- Rotate every 2 years
- Support 2 keys during transition (old + new)
- Include `kid` (Key ID) in JWT header

**Storage:**
- Private key: AWS Secrets Manager / HashiCorp Vault
- Public key: Distributed with application

### HTTPS Requirements

**All endpoints MUST use HTTPS in production**

```
✅ https://license.aegisx.com/api/v1/licenses/activate
❌ http://license.aegisx.com/api/v1/licenses/activate
```

### Request Validation

**All requests must validate:**
- ✅ Content-Type: application/json
- ✅ Request body schema (JSON Schema)
- ✅ Input sanitization (prevent injection)
- ✅ Rate limiting

---

## Client Integration

### Client-Side Validation Flow

```
┌─────────────────────────────────────────┐
│   Application Startup                   │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│   Load license from config/license.key  │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│   Verify JWT signature with public key  │
└─────────────────┬───────────────────────┘
                  │
          ┌───────┴───────┐
          │               │
      Invalid         Valid
          │               │
          ▼               ▼
    ┌─────────┐    ┌──────────┐
    │ Show    │    │ Check    │
    │ Warning │    │ Expiry   │
    └─────────┘    └─────┬────┘
                         │
                    ┌────┴────┐
                    │         │
                Expired   Not Expired
                    │         │
                    ▼         ▼
              ┌─────────┐ ┌────────┐
              │ Warning │ │ Allow  │
              └─────────┘ │ Access │
                          └────────┘
```

### Client Library Interface

**Language-agnostic interface:**

```typescript
// TypeScript/JavaScript
interface LicenseManager {
  // Verify license
  verifyLicense(token: string): LicenseVerificationResult;

  // Get license info
  getLicenseInfo(): LicenseInfo;

  // Check feature access
  hasFeature(feature: string): boolean;

  // Check limit
  checkLimit(resource: string, current: number): boolean;
}

interface LicenseVerificationResult {
  valid: boolean;
  tier: string;
  features: string[];
  limits: Record<string, number>;
  expiresAt?: Date;
  daysRemaining?: number;
  error?: string;
}
```

```python
# Python
class LicenseManager:
    def verify_license(self, token: str) -> dict:
        """Verify license validity"""
        pass

    def get_license_info(self) -> dict:
        """Get license information"""
        pass

    def has_feature(self, feature: str) -> bool:
        """Check if feature is available"""
        pass

    def check_limit(self, resource: str, current: int) -> bool:
        """Check if within limit"""
        pass
```

### Environment Variables (Client)

```bash
# config/.env

# License token (from activation)
LICENSE_TOKEN=eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...

# Public key path
LICENSE_PUBLIC_KEY=/app/config/license_public.pem

# License server URL (for activation/verification)
LICENSE_SERVER_URL=https://license.aegisx.com/api/v1

# Optional: Periodic verification
LICENSE_VERIFY_INTERVAL=2592000  # 30 days in seconds
```

---

## Deployment Architecture

### Recommended Architecture

```
┌──────────────────────────────────────────────────┐
│              Load Balancer (HTTPS)               │
│           license.aegisx.com                     │
└────────────────────┬─────────────────────────────┘
                     │
         ┌───────────┴───────────┐
         │                       │
    ┌────▼─────┐          ┌─────▼────┐
    │ Server 1 │          │ Server 2 │
    │ (Active) │          │(Standby) │
    └────┬─────┘          └─────┬────┘
         │                      │
         └──────────┬───────────┘
                    │
         ┌──────────▼───────────┐
         │   PostgreSQL/MySQL   │
         │    (Primary)         │
         └──────────┬───────────┘
                    │
         ┌──────────▼───────────┐
         │   Redis Cache        │
         │ (Optional)           │
         └──────────────────────┘
```

### Deployment Options

#### Option 1: Traditional VPS/Cloud

**Provider:** DigitalOcean, AWS EC2, Linode

**Specs:**
```yaml
Server:
  CPU: 2 cores
  RAM: 2GB
  Disk: 20GB SSD
  OS: Ubuntu 22.04 LTS

Database:
  CPU: 1 core
  RAM: 2GB
  Disk: 10GB SSD
  Type: PostgreSQL 14 or MySQL 8
```

**Estimated Cost:** ~$20-30/month

#### Option 2: Serverless

**Provider:** AWS Lambda + API Gateway + DynamoDB

```yaml
AWS Services:
  - Lambda (Python 3.12 or Node.js 18)
  - API Gateway (REST API)
  - DynamoDB (licenses table)
  - Secrets Manager (private key)
  - CloudWatch (logs)
```

**Estimated Cost:** ~$5-15/month (pay per use)

#### Option 3: Container (Docker)

**Docker Compose:**
```yaml
version: '3.8'

services:
  license-server:
    image: license-server:latest
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/licenses
      - ADMIN_API_KEY=${ADMIN_API_KEY}
    volumes:
      - ./keys:/app/keys:ro

  db:
    image: postgres:14
    environment:
      - POSTGRES_DB=licenses
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
    volumes:
      - license-db:/var/lib/postgresql/data

volumes:
  license-db:
```

**Kubernetes (Production):**
- 2 replicas (high availability)
- HPA (Horizontal Pod Autoscaler)
- Persistent volume for database

---

## Testing Requirements

### Unit Tests

**Coverage:** Minimum 80%

**Test Cases:**
```
✅ License issuance
  - Valid input
  - Invalid tier
  - Duplicate hospital_code
  - Missing required fields

✅ License activation
  - Valid activation
  - Invalid license_key
  - Hospital code mismatch
  - Activation limit exceeded

✅ License verification
  - Valid token
  - Expired token
  - Invalid signature
  - Revoked license

✅ JWT operations
  - Token generation
  - Token validation
  - Signature verification
  - Expiry handling
```

### Integration Tests

```
✅ API endpoints
  - POST /licenses/issue
  - POST /licenses/activate
  - POST /licenses/verify
  - POST /licenses/revoke
  - POST /licenses/renew
  - GET /licenses
  - GET /licenses/{key}

✅ Database operations
  - Insert license
  - Update license
  - Query licenses
  - Record activation
```

### Load Tests

**Requirements:**
```
Concurrent users: 100
Requests/second: 10
Duration: 5 minutes
Success rate: > 99%
Average response time: < 200ms
```

**Tools:** Apache Bench, k6, Locust

---

## Error Handling

### Standard Error Response Format

```json
{
  "success": false,
  "error": "error_code",
  "message": "Human-readable error message",
  "field": "field_name",  // Optional: for validation errors
  "details": {},  // Optional: additional error details
  "timestamp": "2026-01-17T10:30:00Z",
  "request_id": "req_abc123"  // For debugging
}
```

### Error Codes

```
validation_error       - Invalid input data
unauthorized          - Missing/invalid API key
forbidden             - Access denied
not_found             - Resource not found
conflict              - Resource conflict (duplicate)
rate_limit_exceeded   - Too many requests
server_error          - Internal server error
service_unavailable   - Server maintenance
```

---

## Monitoring & Observability

### Metrics to Track

**Application Metrics:**
```
- Requests per second (by endpoint)
- Response time (p50, p95, p99)
- Error rate (by error code)
- Active licenses count
- Activations per day
- License expiry upcoming (30 days)
```

**Database Metrics:**
```
- Query performance
- Connection pool usage
- Table sizes
```

**Business Metrics:**
```
- New licenses issued (daily/monthly)
- Active vs expired licenses
- Licenses by tier
- Activation success rate
```

### Logging Requirements

**Log Format:** JSON structured logs

```json
{
  "timestamp": "2026-01-17T10:30:00Z",
  "level": "INFO",
  "service": "license-server",
  "endpoint": "/licenses/activate",
  "method": "POST",
  "status_code": 200,
  "duration_ms": 145,
  "license_key": "NHSO-****-****",  // Partially masked
  "hospital_code": "10670",
  "ip_address": "203.x.x.x",
  "user_agent": "Docker/24.0.0",
  "request_id": "req_abc123"
}
```

**Log Retention:**
- Application logs: 30 days
- Audit logs: 1 year
- Access logs: 90 days

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-01-17 | Initial specification |

---

## Implementation Checklist

### Backend Development

- [ ] Setup project structure
- [ ] Implement API endpoints (8 endpoints)
- [ ] Database schema & migrations
- [ ] JWT generation & validation
- [ ] Admin authentication
- [ ] Rate limiting
- [ ] Error handling
- [ ] Unit tests (80% coverage)
- [ ] Integration tests
- [ ] API documentation (OpenAPI/Swagger)

### Security

- [ ] Generate RSA key pair
- [ ] Setup secrets management
- [ ] HTTPS configuration
- [ ] Input validation
- [ ] SQL injection prevention
- [ ] XSS protection
- [ ] CORS configuration

### Deployment

- [ ] Dockerfile
- [ ] docker-compose.yml
- [ ] Environment variables
- [ ] Database backup strategy
- [ ] CI/CD pipeline
- [ ] Monitoring setup
- [ ] Log aggregation

### Documentation

- [ ] API documentation
- [ ] Deployment guide
- [ ] Admin manual
- [ ] Client integration guide

---

**Ready for Implementation!** 🚀

Choose your stack:
- ✅ Python (Flask/FastAPI)
- ✅ Node.js (Express/Fastify)
- ✅ Go (Gin/Echo)
- ✅ Any language with HTTP + JWT support
