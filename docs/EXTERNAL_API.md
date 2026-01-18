# External API Documentation

## Overview

E-Claim HIS Integration API provides RESTful endpoints for integrating hospital HIS systems with E-Claim data.

## Quick Start

### 1. Access Swagger UI

Interactive API documentation: **http://localhost:5001/api/docs**

### 2. Download OpenAPI Spec

- YAML: `http://localhost:5001/api/v1/openapi.yaml`
- JSON: `http://localhost:5001/api/v1/openapi.json`

Import into Postman, Insomnia, or any OpenAPI-compatible tool.

### 3. Generate API Key

1. Login to admin panel: http://localhost:5001/login
2. Navigate to Settings → API Keys
3. Click Generate New API Key
4. Copy the key (shown only once)

### 4. Make API Calls

Include API key in request headers:

```bash
curl -H "X-API-Key: your-api-key" \
  "http://localhost:5001/api/v1/claims?date_from=2025-12-01&date_to=2025-12-31"
```

## Available Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| /api/v1/health | GET | Health check (no auth) |
| /api/v1/claims | GET | Get claims data |
| /api/v1/claims/{tran_id} | GET | Get single claim |
| /api/v1/claims/summary | GET | Get claims summary |
| /api/v1/reconciliation/match | POST | Match claims with HIS |
| /api/v1/reconciliation/status | GET | Get reconciliation status |
| /api/v1/imports/status | GET | Get import status |

## Authentication

All endpoints (except /health) require API key:

```
X-API-Key: your-api-key-here
```

## Example Usage

### Python

```python
import requests

headers = {'X-API-Key': 'your-api-key'}
response = requests.get(
    'http://localhost:5001/api/v1/claims',
    headers=headers,
    params={'date_from': '2025-12-01', 'date_to': '2025-12-31'}
)
print(response.json())
```

### cURL

```bash
curl -H "X-API-Key: your-api-key" \
  "http://localhost:5001/api/v1/claims?date_from=2025-12-01&date_to=2025-12-31"
```

## Rate Limits

- 100 requests per minute per API key
- 1000 requests per hour per API key

## Support

- GitHub: https://github.com/aegisx-platform/eclaim-rep-download
- Documentation: See `/api/docs` for full API reference

