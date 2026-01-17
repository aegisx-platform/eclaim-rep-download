# HIS Integration Guide

> Technical Guide for Integrating E-Claim System with Hospital Information Systems

## Overview

This guide provides technical documentation for integrating the E-Claim REP Download System with your Hospital Information System (HIS) using REST APIs.

## Integration Benefits

- **Real-time Data Sync:** E-Claim status visible in HIS immediately
- **Automated Reconciliation:** Auto-match claims by VN/HN/PID (90% time savings)
- **Proactive Alerts:** Denied claims flagged in HIS for faster follow-up
- **Unified Dashboard:** Single source of truth for claims data
- **PDPA Compliant:** Full audit trail of all data access

## Quick Start

### 1. Generate API Key

```bash
docker-compose exec web python << 'EOF'
from utils.api_auth import generate_api_key
key = generate_api_key(
    name='HIS Integration',
    scopes=['claims:read', 'reconciliation:read']
)
print(f'API Key: {key}')
EOF
```

### 2. Test Connectivity

```bash
curl -H "Authorization: Bearer YOUR_API_KEY" \
     http://eclaim-server:5001/api/health
```

### 3. Basic Integration Example

```python
import requests

ECLAIM_API = 'http://eclaim-server:5001/api'
API_KEY = 'YOUR_API_KEY'

def get_claim_status(vn):
    """Get E-Claim status for a visit number"""
    response = requests.get(
        f'{ECLAIM_API}/claims/{vn}/eclaim-status',
        headers={'Authorization': f'Bearer {API_KEY}'}
    )
    return response.json()

# Example usage
status = get_claim_status('67010012345')
if status['found']:
    print(f"Status: {status['eclaim_data']['status']}")
    print(f"Amount: {status['eclaim_data']['approved_amount']}")
```

## Core API Endpoints

### Get Claim Status by VN

**Endpoint:** `GET /api/claims/<vn>/eclaim-status`

**Response:**
```json
{
    "found": true,
    "vn": "67010012345",
    "eclaim_data": {
        "status": "approved",
        "claimed_amount": 1250.00,
        "approved_amount": 1250.00,
        "payment_date": "2025-02-10"
    }
}
```

### Reconciliation API

**Endpoint:** `POST /api/analytics/reconciliation`

**Purpose:** Batch reconcile HIS data with E-Claim data

**Request:**
```json
{
    "date_start": "2025-01-01",
    "date_end": "2025-01-31",
    "his_data": [
        {
            "vn": "67010012345",
            "total_charge": 1250.00
        }
    ]
}
```

**Response:**
```json
{
    "summary": {
        "matched": 8200,
        "unmatched_eclaim": 220,
        "unmatched_his": 250,
        "discrepancies": 80
    },
    "matched_records": [...],
    "discrepancies": [...]
}
```

## Integration Patterns

### Pattern 1: Polling (Simple)

HIS polls for updates every 5-15 minutes:

```python
# Cron job: run every 5 minutes
import requests
from datetime import datetime

last_check = load_last_check_time()
response = requests.get(
    f'{ECLAIM_API}/claims/recent',
    params={'since': last_check},
    headers={'Authorization': f'Bearer {API_KEY}'}
)

for claim in response.json()['data']:
    update_his_database(claim)

save_last_check_time(datetime.now())
```

### Pattern 2: Webhooks (Recommended)

E-Claim pushes updates to HIS in real-time:

```python
# In HIS system
from flask import Flask, request

app = Flask(__name__)

@app.route('/api/eclaim-webhook', methods=['POST'])
def handle_webhook():
    data = request.json

    if data['event'] == 'claim.denied':
        # Update HIS + send alert
        update_claim_status(data['vn'], 'denied')
        send_denial_alert(data['vn'], data['denial_reason'])

    return {'status': 'success'}
```

## Field Mappings

| E-Claim | HIS (Common Names) | Type |
|---------|-------------------|------|
| VN | vn, visit_number | VARCHAR(20) |
| HN | hn, hospital_number | VARCHAR(20) |
| PID/CID | pid, national_id | VARCHAR(13) |
| TRAN_ID | eclaim_tran_id | VARCHAR(20) |
| TOTAL | total_charge, claim_amount | DECIMAL(10,2) |
| INSCL | fund_type (UC/SSS/CSMBS) | VARCHAR(10) |

## Security

### Authentication
- API Key (Bearer token) - recommended
- IP Whitelisting
- TLS/HTTPS in production

### Example with API Key:
```http
GET /api/claims/recent
Authorization: Bearer sk_live_abc123xyz...
```

## Error Handling

### HTTP Status Codes
- `200` - Success
- `400` - Bad Request (invalid params)
- `401` - Unauthorized (invalid API key)
- `404` - Not Found
- `429` - Rate Limit Exceeded
- `500` - Server Error

### Retry Logic
```python
import time

def call_with_retry(url, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code in [429, 500, 503]:
                if attempt < max_retries - 1:
                    wait = 2 ** attempt  # 1s, 2s, 4s
                    time.sleep(wait)
                    continue
            raise
```

## Common HIS Examples

### HOSxP (PHP)
```php
function get_eclaim_status($vn) {
    $url = ECLAIM_API . "/claims/$vn/eclaim-status";
    $ch = curl_init($url);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_HTTPHEADER, [
        'Authorization: Bearer ' . ECLAIM_API_KEY
    ]);
    $response = curl_exec($ch);
    return json_decode($response, true);
}
```

### Thai HIS (Java)
```java
public JSONObject getEClaimStatus(String vn) {
    HttpClient client = HttpClient.newHttpClient();
    HttpRequest request = HttpRequest.newBuilder()
        .uri(URI.create(ECLAIM_API + "/claims/" + vn + "/eclaim-status"))
        .header("Authorization", "Bearer " + API_KEY)
        .GET()
        .build();

    HttpResponse<String> response = client.send(request,
        HttpResponse.BodyHandlers.ofString());

    return new JSONObject(response.body());
}
```

## Testing Checklist

- [ ] Connectivity test: `curl http://eclaim-server:5001/api/health`
- [ ] Authentication test with API key
- [ ] Single claim lookup: `/api/claims/<vn>/eclaim-status`
- [ ] Reconciliation API test
- [ ] Error handling (invalid VN, invalid API key)
- [ ] Performance benchmark (expected: 100-200 req/s)

## Support

- **Documentation:** https://docs.eclaim-system.com
- **API Reference:** https://eclaim-server:5001/api/docs
- **Integration Support:** integration@eclaim-system.com
- **GitHub Issues:** https://github.com/aegisx-platform/eclaim-rep-download/issues

---

**Document Version:** 1.0  
**Last Updated:** 2026-01-17  
**Owner:** Integration & API Team
