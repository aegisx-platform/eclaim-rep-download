# Master Data API Routes - Complete List

## Blueprint Information
- **File**: `routes/master_data_api.py`
- **Blueprint Name**: `master_data_api_bp`
- **Total Routes**: 17

---

## Health Offices API Routes (5 routes)

### 1. List Health Offices
```
GET /api/health-offices
```
**Description**: Get health offices with filtering and pagination
**Authentication**: None (public)
**Query Parameters**:
- `search` - Search in name, hcode5, hcode9
- `province` - Filter by province
- `status` - Filter by status
- `level` - Filter by hospital level
- `region` - Filter by health region
- `page` - Page number (default: 1)
- `per_page` - Results per page (default: 50)

**Response**:
```json
{
  "success": true,
  "data": [...],
  "total": 1234,
  "page": 1,
  "per_page": 50,
  "total_pages": 25
}
```

---

### 2. Health Offices Statistics
```
GET /api/health-offices/stats
```
**Description**: Get health offices statistics
**Authentication**: None (public)
**Response**: Statistics by status, level, region, province

---

### 3. Import Health Offices
```
POST /api/health-offices/import
```
**Description**: Import health offices from uploaded Excel file
**Authentication**: None (public)
**Content-Type**: `multipart/form-data`
**Form Data**:
- `file` - Excel file (.xlsx)
- `mode` - Import mode: 'upsert' or 'replace' (default: 'upsert')

**Response**:
```json
{
  "success": true,
  "message": "Import completed",
  "total": 1000,
  "imported": 950,
  "updated": 0,
  "skipped": 40,
  "errors": 10,
  "duration": 12.5
}
```

---

### 4. Clear Health Offices
```
POST /api/health-offices/clear
```
**Description**: Clear all health offices data
**Authentication**: None (public)
**Response**: Confirmation with remaining count

---

### 5. Lookup Health Office
```
GET /api/health-offices/lookup/<code>
```
**Description**: Lookup health office by code (hcode5 or hcode9)
**Authentication**: None (public)
**URL Parameters**:
- `code` - Hospital code (5 or 9 digits)

**Response**:
```json
{
  "success": true,
  "data": {
    "id": 1,
    "name": "โรงพยาบาลตัวอย่าง",
    "hcode5": "10001",
    "hcode9": "100010001",
    "hospital_level": "S",
    "actual_beds": 100,
    ...
  }
}
```

---

## Master Data Count APIs (5 routes)

All count routes require `@login_required` authentication.

### 6. Health Offices Count
```
GET /api/master-data/health-offices/count
```
**Description**: Get count of health offices
**Authentication**: Required (`@login_required`)
**Response**: `{"success": true, "count": 1234}`

---

### 7. Error Codes Count
```
GET /api/master-data/error-codes/count
```
**Description**: Get count of NHSO error codes
**Authentication**: Required (`@login_required`)
**Response**: `{"success": true, "count": 567}`

---

### 8. Fund Types Count
```
GET /api/master-data/fund-types/count
```
**Description**: Get count of fund types
**Authentication**: Required (`@login_required`)
**Response**: `{"success": true, "count": 15}`

---

### 9. Service Types Count
```
GET /api/master-data/service-types/count
```
**Description**: Get count of service types
**Authentication**: Required (`@login_required`)
**Response**: `{"success": true, "count": 20}`

---

### 10. Dim Date Count
```
GET /api/master-data/dim-date/count
```
**Description**: Get count of date dimension records
**Authentication**: Required (`@login_required`)
**Response**: `{"success": true, "count": 2557}`

---

## Master Data List APIs (7 routes)

All list routes require `@login_required` authentication and support pagination.

### 11. List Error Codes
```
GET /api/master-data/error-codes
```
**Description**: Get NHSO error codes with pagination
**Authentication**: Required (`@login_required`)
**Query Parameters**:
- `page` - Page number (default: 1)
- `per_page` - Results per page (default: 50)
- `search` - Search in code, type, description
- `category` - Filter by error type/category

**Response**:
```json
{
  "success": true,
  "data": [
    {
      "error_code": "E001",
      "error_message": "Invalid PID",
      "category": "validation",
      "description": "Patient ID format error"
    }
  ],
  "total": 567
}
```

---

### 12. Get Error Code by Code
```
GET /api/master-data/error-codes/<code>
```
**Description**: Get error code details by code
**Authentication**: Required (`@login_required`)
**URL Parameters**:
- `code` - Error code (e.g., "E001")

**Response**:
```json
{
  "success": true,
  "data": {
    "error_code": "E001",
    "error_message": "Invalid PID",
    "category": "validation",
    "guide": "Check patient ID format..."
  }
}
```

---

### 13. List Fund Types
```
GET /api/master-data/fund-types
```
**Description**: Get fund types with pagination
**Authentication**: Required (`@login_required`)
**Query Parameters**:
- `page` - Page number (default: 1)
- `per_page` - Results per page (default: 50)
- `search` - Search in fund_code, fund_name_th

**Response**:
```json
{
  "success": true,
  "data": [
    {
      "fund_code": "UC",
      "fund_name": "หลักประกันสุขภาพถ้วนหน้า",
      "short_name": "UCS",
      "description": "...",
      "is_active": true
    }
  ],
  "total": 15
}
```

---

### 14. List Service Types
```
GET /api/master-data/service-types
```
**Description**: Get service types with pagination
**Authentication**: Required (`@login_required`)
**Query Parameters**:
- `page` - Page number (default: 1)
- `per_page` - Results per page (default: 50)
- `search` - Search in service_code, service_name_th

**Response**:
```json
{
  "success": true,
  "data": [
    {
      "service_code": "OP",
      "service_name": "ผู้ป่วยนอก",
      "short_name": "OPD",
      "description": "...",
      "is_active": true
    }
  ],
  "total": 20
}
```

---

### 15. List Date Dimension
```
GET /api/master-data/dim-date
```
**Description**: Get date dimension with pagination
**Authentication**: Required (`@login_required`)
**Query Parameters**:
- `page` - Page number (default: 1)
- `per_page` - Results per page (default: 50)
- `month` - Filter by month (format: YYYY-MM)
- `year_be` - Filter by Buddhist Era year
- `quarter` - Filter by quarter (1-4)
- `fiscal_year` - Filter by fiscal year (Buddhist Era)

**Response**:
```json
{
  "success": true,
  "data": [
    {
      "date_value": "2025-01-19",
      "date_be": "25680119",
      "year_be": 2568,
      "month_name_th": "มกราคม",
      "quarter": 2,
      "fiscal_year_be": 2568,
      "week_of_year": 3,
      "day_name_th": "วันอาทิตย์"
    }
  ],
  "total": 2557
}
```

---

### 16. Date Dimension Coverage
```
GET /api/master-data/dim-date/coverage
```
**Description**: Get date dimension coverage information
**Authentication**: Required (`@login_required`)

**Response**:
```json
{
  "success": true,
  "data": {
    "earliest_date": "2020-01-01",
    "latest_date": "2026-12-31",
    "earliest_year_be": 2563,
    "latest_year_be": 2569,
    "total_records": 2557,
    "coverage_days": 2557,
    "has_data": true
  }
}
```

---

### 17. Generate Date Dimension
```
POST /api/master-data/dim-date/generate
```
**Description**: Generate date dimension data for future years
**Authentication**: Required (`@login_required`)
**Content-Type**: `application/json`
**Request Body**:
```json
{
  "target_year": 2027
}
```

**Response**:
```json
{
  "success": true,
  "message": "Generated 365 new records up to year 2027 (BE 2570)",
  "records_added": 365,
  "target_year": 2027,
  "target_year_be": 2570
}
```

**Validation**:
- `target_year` must be >= current year
- `target_year` must be within 20 years from now

---

## Database Tables

| Route Group | Tables Used |
|------------|-------------|
| Health Offices | `health_offices`, `health_offices_import_log` |
| Error Codes | `nhso_error_codes` |
| Fund Types | `fund_types` |
| Service Types | `service_types` |
| Date Dimension | `dim_date` |

---

## Authentication Summary

| Route Pattern | Authentication |
|--------------|----------------|
| `/api/health-offices/*` | None (public) |
| `/api/master-data/*` | Required (`@login_required`) |

---

## Error Responses

All routes return standard error format:
```json
{
  "success": false,
  "error": "Error message description"
}
```

Common HTTP status codes:
- `200` - Success
- `400` - Bad request (validation error)
- `404` - Not found
- `500` - Server error

---

## Notes

1. All routes use database connection pooling via `get_db_connection()`
2. PostgreSQL and MySQL compatibility via `DB_TYPE` checks
3. Thai Buddhist Era (BE) dates are converted from Gregorian dates (add 543)
4. Pagination uses `page` and `per_page` parameters consistently
5. Search uses case-insensitive matching (ILIKE for PostgreSQL, LIKE for MySQL)
