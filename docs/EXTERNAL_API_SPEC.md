# External API Specification

## Overview

External API สำหรับให้ระบบ HIS ของโรงพยาบาลเชื่อมต่อกับ E-Claim Revenue Intelligence System

**Base URL:** `http(s)://[server]/api/v1`

**Authentication:** API Key via header
```
X-API-Key: your_api_key_here
```
หรือ
```
Authorization: Bearer your_api_key_here
```

## Rate Limits

- **Default:** 100 requests per minute per API key
- **Burst:** 20 requests per second

## API Endpoints

### 1. Health Check

#### GET `/api/v1/health`

ตรวจสอบสถานะ API

**Authentication:** Not required

**Response:**
```json
{
  "success": true,
  "message": "API is healthy",
  "version": "1.0.0",
  "timestamp": "2026-01-17T22:45:00Z"
}
```

---

### 2. Claims Data

#### GET `/api/v1/claims`

ดึงข้อมูล claims (REP) พร้อม filters

**Authentication:** Required

**Query Parameters:**
- `date_from` (string, required): วันที่เริ่มต้น (YYYY-MM-DD)
- `date_to` (string, required): วันที่สิ้นสุด (YYYY-MM-DD)
- `scheme` (string, optional): รหัสสิทธิ (ucs, ofc, sss, lgo)
- `hn` (string, optional): HN ของผู้ป่วย
- `pid` (string, optional): เลขบัตรประชาชน
- `page` (integer, optional, default=1): หน้า
- `per_page` (integer, optional, default=100, max=1000): จำนวนต่อหน้า

**Response:**
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "tran_id": "1234567890",
        "file_id": 123,
        "hn": "12345678",
        "pid": "1234567890123",
        "dateadm": "2025-12-01",
        "datedsc": "2025-12-02",
        "an": "65120001",
        "repno": "REP001",
        "total_approve": 5000.00,
        "hcode": "10670",
        "hmain": "สปสช 10 กทม",
        "scheme_code": "UCS",
        "his_matched": false,
        "his_vn": null,
        "reconcile_status": "unmatched"
      }
    ],
    "pagination": {
      "page": 1,
      "per_page": 100,
      "total": 1500,
      "pages": 15
    }
  }
}
```

**Error Response:**
```json
{
  "success": false,
  "error": "Invalid date range",
  "code": "INVALID_PARAMS"
}
```

---

#### GET `/api/v1/claims/{tran_id}`

ดึงข้อมูล claim รายการเดียว

**Authentication:** Required

**Path Parameters:**
- `tran_id` (string, required): TRAN_ID ของ claim

**Response:**
```json
{
  "success": true,
  "data": {
    "tran_id": "1234567890",
    "file_id": 123,
    "hn": "12345678",
    "pid": "1234567890123",
    "dateadm": "2025-12-01",
    "datedsc": "2025-12-02",
    "an": "65120001",
    "vn": "6512000001",
    "total_approve": 5000.00,
    "scheme_code": "UCS",
    "his_matched": false,
    "reconcile_status": "unmatched"
  }
}
```

---

#### GET `/api/v1/claims/summary`

สรุปข้อมูล claims

**Authentication:** Required

**Query Parameters:**
- `date_from` (string, required): วันที่เริ่มต้น (YYYY-MM-DD)
- `date_to` (string, required): วันที่สิ้นสุด (YYYY-MM-DD)
- `scheme` (string, optional): รหัสสิทธิ

**Response:**
```json
{
  "success": true,
  "data": {
    "total_claims": 1500,
    "total_amount": 7500000.00,
    "by_scheme": {
      "UCS": {"count": 1000, "amount": 5000000.00},
      "OFC": {"count": 300, "amount": 1500000.00},
      "SSS": {"count": 150, "amount": 750000.00},
      "LGO": {"count": 50, "amount": 250000.00}
    },
    "reconciliation": {
      "matched": 1200,
      "unmatched": 300,
      "match_rate": 0.80
    }
  }
}
```

---

### 3. Reconciliation

#### POST `/api/v1/reconciliation/match`

ส่งข้อมูลจาก HIS เพื่อทำการกระทบยอดกับ E-Claim

**Authentication:** Required

**Request Body:**
```json
{
  "matches": [
    {
      "tran_id": "1234567890",
      "his_vn": "6512000001",
      "his_hn": "12345678",
      "his_an": "65120001",
      "his_admission_date": "2025-12-01",
      "his_discharge_date": "2025-12-02",
      "his_total_charge": 5500.00
    }
  ]
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "matched": 50,
    "failed": 2,
    "results": [
      {
        "tran_id": "1234567890",
        "status": "matched",
        "his_vn": "6512000001"
      },
      {
        "tran_id": "1234567891",
        "status": "failed",
        "error": "TRAN_ID not found"
      }
    ]
  }
}
```

---

#### GET `/api/v1/reconciliation/status`

ดูสถานะการกระทบยอด

**Authentication:** Required

**Query Parameters:**
- `date_from` (string, optional): วันที่เริ่มต้น
- `date_to` (string, optional): วันที่สิ้นสุด

**Response:**
```json
{
  "success": true,
  "data": {
    "total_records": 1500,
    "matched": 1200,
    "unmatched": 300,
    "match_rate": 0.80,
    "last_sync": "2026-01-17T22:30:00Z"
  }
}
```

---

### 4. Import Status

#### GET `/api/v1/imports/status`

ดูสถานะการ import ล่าสุด

**Authentication:** Required

**Response:**
```json
{
  "success": true,
  "data": {
    "rep": {
      "total_files": 807,
      "imported": 807,
      "failed": 0,
      "last_import": "2026-01-17T22:00:00Z"
    },
    "stm": {
      "total_files": 123,
      "imported": 123,
      "failed": 0,
      "last_import": "2026-01-17T21:30:00Z"
    },
    "smt": {
      "total_records": 4475,
      "total_amount": 6714700000.00,
      "last_sync": "2026-01-17"
    }
  }
}
```

---

#### GET `/api/v1/imports/history`

ประวัติการ import

**Authentication:** Required

**Query Parameters:**
- `type` (string, optional): ประเภทไฟล์ (rep, stm, smt)
- `page` (integer, optional, default=1)
- `per_page` (integer, optional, default=50, max=100)

**Response:**
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": 123,
        "filename": "REP_2025_12_UCS.xls",
        "file_type": "rep",
        "status": "completed",
        "records_imported": 150,
        "import_date": "2026-01-17T20:00:00Z"
      }
    ],
    "pagination": {
      "page": 1,
      "per_page": 50,
      "total": 807,
      "pages": 17
    }
  }
}
```

---

### 5. Files

#### GET `/api/v1/files`

รายการไฟล์ที่ import แล้ว

**Authentication:** Required

**Query Parameters:**
- `type` (string, optional): ประเภท (rep, stm, smt)
- `status` (string, optional): สถานะ (completed, failed, processing)
- `page` (integer, optional)
- `per_page` (integer, optional)

**Response:**
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": 123,
        "filename": "REP_2025_12_UCS.xls",
        "file_type": "rep",
        "status": "completed",
        "records": 150,
        "size_bytes": 524288,
        "created_at": "2026-01-17T20:00:00Z"
      }
    ],
    "pagination": {
      "page": 1,
      "per_page": 50,
      "total": 807,
      "pages": 17
    }
  }
}
```

---

#### GET `/api/v1/files/{file_id}`

รายละเอียดไฟล์

**Authentication:** Required

**Path Parameters:**
- `file_id` (integer, required): ID ของไฟล์

**Response:**
```json
{
  "success": true,
  "data": {
    "id": 123,
    "filename": "REP_2025_12_UCS.xls",
    "file_type": "rep",
    "status": "completed",
    "records_total": 150,
    "records_imported": 150,
    "records_failed": 0,
    "size_bytes": 524288,
    "import_started_at": "2026-01-17T20:00:00Z",
    "import_completed_at": "2026-01-17T20:05:00Z",
    "error_message": null
  }
}
```

---

## Error Codes

| Code | Description |
|------|-------------|
| `INVALID_API_KEY` | API key ไม่ถูกต้องหรือหมดอายุ |
| `RATE_LIMIT_EXCEEDED` | เกินจำนวนครั้งที่กำหนด |
| `INVALID_PARAMS` | พารามิเตอร์ไม่ถูกต้อง |
| `NOT_FOUND` | ไม่พบข้อมูล |
| `INTERNAL_ERROR` | เกิดข้อผิดพลาดภายในระบบ |
| `UNAUTHORIZED` | ไม่มีสิทธิ์เข้าถึง |

## Response Format

ทุก response จะอยู่ในรูปแบบ:

**Success:**
```json
{
  "success": true,
  "data": {...}
}
```

**Error:**
```json
{
  "success": false,
  "error": "Error message",
  "code": "ERROR_CODE"
}
```

## Webhooks (Future)

- POST callback เมื่อมีการ import ไฟล์ใหม่
- POST callback เมื่อมีการกระทบยอดสำเร็จ
