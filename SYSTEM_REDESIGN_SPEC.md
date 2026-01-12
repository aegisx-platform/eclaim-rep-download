# System Redesign Specification
## E-Claim Download & Import System - Architecture Separation

**Version:** 1.0
**Date:** 2026-01-12
**Author:** Claude Opus 4.5

---

## 1. Executive Summary

### 1.1 Current State
ระบบปัจจุบันมี 3 ประเภทการ download ที่รวมอยู่ใน repo เดียวกัน:

| ประเภท | แหล่งข้อมูล | ประเภทไฟล์ | ต้อง Login |
|--------|------------|-----------|-----------|
| **REP** (Representative) | NHSO E-Claim Portal | Excel (.xls) | ✅ Yes |
| **STM** (Statement) | NHSO E-Claim Portal | Excel (.xls) | ✅ Yes |
| **SMT** (Budget Report) | SMT API (Public) | JSON/CSV | ❌ No |

### 1.2 Goals
1. **แยก Free Version** - Download system ที่สามารถใช้งานแบบ standalone
2. **Paid Version** - Full features (import, reconciliation, analytics, scheduling)
3. **Shared Core** - Logic ที่ใช้ร่วมกันได้ทั้ง 2 repos
4. **API Ready** - มี REST API สำหรับ integration กับระบบอื่น

---

## 2. Current System Analysis

### 2.1 Download Flow Diagram (Current)

```
┌─────────────────────────────────────────────────────────────────┐
│                    CURRENT MONOLITHIC SYSTEM                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐ │
│  │  REP Downloader │   │  STM Downloader │   │   SMT Fetcher   │ │
│  │    (eclaim)     │   │   (statement)   │   │    (budget)     │ │
│  └────────┬────────┘   └────────┬────────┘   └────────┬────────┘ │
│           │                     │                     │           │
│           └─────────────────────┼─────────────────────┘           │
│                                 │                                 │
│                                 ↓                                 │
│  ┌──────────────────────────────────────────────────────────────┐│
│  │                     Flask Web Application                     ││
│  │  ├─ Dashboard      ├─ File Management    ├─ Settings         ││
│  │  ├─ Import System  ├─ Reconciliation     ├─ Scheduler        ││
│  │  └─ Real-time Logs └─ Analytics          └─ API Endpoints    ││
│  └──────────────────────────────────────────────────────────────┘│
│                                 │                                 │
│                                 ↓                                 │
│  ┌──────────────────────────────────────────────────────────────┐│
│  │                        Database Layer                         ││
│  │  ├─ eclaim_imported_files    ├─ claim_rep_opip_nhso_item     ││
│  │  ├─ stm_imported_files       ├─ stm_claim_items              ││
│  │  └─ smt_budget_items         └─ health_offices               ││
│  └──────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Component Dependencies

```
┌─────────────────────────────────────────────────────────────────┐
│                    DEPENDENCY ANALYSIS                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  DOWNLOAD LAYER (Can be standalone)                              │
│  ═══════════════════════════════════                              │
│  ├─ eclaim_downloader_http.py  → HistoryManager, LogStreamer     │
│  ├─ stm_downloader_http.py     → HistoryManager, LogStreamer     │
│  ├─ smt_budget_fetcher.py      → LogStreamer, (optional DB)      │
│  ├─ bulk_downloader.py         → eclaim_downloader_http          │
│  └─ download_with_import.py    → eclaim_downloader + importer    │
│                                                                   │
│  IMPORT LAYER (Paid feature)                                     │
│  ═══════════════════════════                                      │
│  ├─ eclaim_import.py           → importer_v2, parser             │
│  ├─ stm_import.py              → stm_importer, parser            │
│  └─ utils/eclaim/importer_v2   → Database connection             │
│                                                                   │
│  APPLICATION LAYER (Paid feature)                                │
│  ══════════════════════════════                                   │
│  ├─ app.py                     → All components                  │
│  ├─ Scheduler                  → All downloaders                 │
│  ├─ Reconciliation             → Database queries                │
│  └─ Analytics                  → Aggregated data                 │
│                                                                   │
│  SHARED UTILITIES (Both versions)                                │
│  ═════════════════════════════════                                │
│  ├─ utils/history_manager.py   → JSON file operations            │
│  ├─ utils/log_stream.py        → Logging infrastructure          │
│  ├─ utils/settings_manager.py  → Configuration management        │
│  └─ utils/file_manager.py      → Safe file operations            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Proposed Architecture

### 3.1 Two-Tier Repository Structure

```
┌─────────────────────────────────────────────────────────────────┐
│                    PROPOSED ARCHITECTURE                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │           REPO 1: eclaim-downloader-core (FREE)              │ │
│  │           ══════════════════════════════════════              │ │
│  │                                                               │ │
│  │   Features:                                                   │ │
│  │   ├─ REP Download (OP, IP, ORF files)                        │ │
│  │   ├─ STM Download (Statement files)                          │ │
│  │   ├─ SMT Fetch (Budget API - no auth needed)                 │ │
│  │   ├─ History Tracking (JSON-based)                           │ │
│  │   ├─ CLI Tools                                               │ │
│  │   ├─ Simple Web UI (view/download only)                      │ │
│  │   └─ REST API (read-only)                                    │ │
│  │                                                               │ │
│  │   Limitations:                                                │ │
│  │   ✗ No database import                                       │ │
│  │   ✗ No reconciliation                                        │ │
│  │   ✗ No scheduler                                             │ │
│  │   ✗ No analytics                                             │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                              │                                    │
│                              │ pip install / git submodule        │
│                              ↓                                    │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │          REPO 2: eclaim-platform-pro (PAID)                  │ │
│  │          ══════════════════════════════════                   │ │
│  │                                                               │ │
│  │   Includes all FREE features PLUS:                           │ │
│  │   ├─ Database Import System                                  │ │
│  │   │   ├─ REP Import (OPIP, ORF tables)                       │ │
│  │   │   ├─ STM Import (Statement tables)                       │ │
│  │   │   └─ SMT Save to DB                                      │ │
│  │   ├─ Scheduler (APScheduler)                                 │ │
│  │   │   ├─ Scheduled downloads                                 │ │
│  │   │   └─ Auto-import after download                          │ │
│  │   ├─ Reconciliation Dashboard                                │ │
│  │   │   ├─ REP vs STM comparison                               │ │
│  │   │   └─ Monthly/Yearly reports                              │ │
│  │   ├─ Analytics & Reports                                     │ │
│  │   │   ├─ Claim statistics                                    │ │
│  │   │   └─ Fund analysis                                       │ │
│  │   ├─ Advanced API (write operations)                         │ │
│  │   └─ Multi-user support (future)                             │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Module Separation Strategy

```
┌─────────────────────────────────────────────────────────────────┐
│               MODULE SEPARATION STRATEGY                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  STRATEGY A: Git Submodule (Recommended)                         │
│  ════════════════════════════════════════                         │
│                                                                   │
│  eclaim-platform-pro/                                            │
│  ├─ lib/eclaim-downloader-core/  ← git submodule                 │
│  │   ├─ downloaders/                                             │
│  │   ├─ utils/                                                   │
│  │   └─ api/                                                     │
│  ├─ src/                                                         │
│  │   ├─ importers/                                               │
│  │   ├─ scheduler/                                               │
│  │   └─ reconciliation/                                          │
│  └─ app.py                                                       │
│                                                                   │
│  STRATEGY B: Python Package (PyPI/Private Registry)             │
│  ═══════════════════════════════════════════════════              │
│                                                                   │
│  # In eclaim-platform-pro/requirements.txt                       │
│  eclaim-downloader-core @ git+https://github.com/.../core.git    │
│  # OR                                                            │
│  eclaim-downloader-core>=1.0.0  # From PyPI                      │
│                                                                   │
│  STRATEGY C: Monorepo with Packages (pnpm-style)                │
│  ═══════════════════════════════════════════════                  │
│                                                                   │
│  eclaim-platform/                                                │
│  ├─ packages/                                                    │
│  │   ├─ core/           ← Free, published separately             │
│  │   ├─ pro/            ← Paid features                          │
│  │   └─ shared/         ← Common utilities                       │
│  └─ apps/                                                        │
│      ├─ free-app/       ← Uses core only                         │
│      └─ pro-app/        ← Uses all packages                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Detailed Module Design

### 4.1 FREE Version - Core Module Structure

```
eclaim-downloader-core/
├── README.md
├── LICENSE                    # MIT or similar
├── pyproject.toml             # Package definition
├── requirements.txt
│
├── eclaim_core/               # Main package
│   ├── __init__.py
│   │
│   ├── downloaders/           # Download implementations
│   │   ├── __init__.py
│   │   ├── base.py            # BaseDownloader abstract class
│   │   ├── rep.py             # REPDownloader (OP, IP, ORF)
│   │   ├── stm.py             # STMDownloader (Statement)
│   │   └── smt.py             # SMTFetcher (Budget API)
│   │
│   ├── auth/                  # Authentication
│   │   ├── __init__.py
│   │   ├── session.py         # Session management
│   │   └── credentials.py     # Credential loader
│   │
│   ├── history/               # Download tracking
│   │   ├── __init__.py
│   │   ├── manager.py         # HistoryManager
│   │   └── models.py          # DownloadRecord dataclass
│   │
│   ├── logging/               # Logging infrastructure
│   │   ├── __init__.py
│   │   ├── streamer.py        # LogStreamer
│   │   └── formatters.py      # JSON/Console formatters
│   │
│   ├── config/                # Configuration
│   │   ├── __init__.py
│   │   ├── settings.py        # SettingsManager
│   │   └── defaults.py        # Default values
│   │
│   └── api/                   # REST API (Flask Blueprint)
│       ├── __init__.py
│       ├── routes.py          # API endpoints
│       └── schemas.py         # Request/Response models
│
├── cli/                       # Command-line tools
│   ├── download_rep.py        # python -m cli.download_rep
│   ├── download_stm.py
│   ├── fetch_smt.py
│   └── bulk_download.py
│
├── web/                       # Simple Web UI
│   ├── app.py                 # Minimal Flask app
│   ├── templates/
│   │   ├── base.html
│   │   ├── dashboard.html     # View-only dashboard
│   │   └── files.html
│   └── static/
│
├── tests/
│   ├── test_downloaders.py
│   ├── test_history.py
│   └── test_api.py
│
└── docker/
    ├── Dockerfile
    └── docker-compose.yml
```

### 4.2 PAID Version - Pro Module Structure

```
eclaim-platform-pro/
├── README.md
├── LICENSE                    # Commercial License
├── pyproject.toml
├── requirements.txt           # Includes eclaim-downloader-core
│
├── lib/
│   └── eclaim-downloader-core/  # Git submodule OR pip install
│
├── eclaim_pro/                # Pro package
│   ├── __init__.py
│   │
│   ├── importers/             # Database import
│   │   ├── __init__.py
│   │   ├── base.py            # BaseImporter
│   │   ├── rep.py             # REPImporter (OPIP, ORF)
│   │   ├── stm.py             # STMImporter
│   │   └── smt.py             # SMTImporter
│   │
│   ├── database/              # Database layer
│   │   ├── __init__.py
│   │   ├── connection.py      # Connection pooling
│   │   ├── models.py          # SQLAlchemy models (optional)
│   │   └── migrations/        # Alembic migrations
│   │
│   ├── scheduler/             # Job scheduling
│   │   ├── __init__.py
│   │   ├── manager.py         # SchedulerManager
│   │   └── jobs.py            # Job definitions
│   │
│   ├── reconciliation/        # Reconciliation logic
│   │   ├── __init__.py
│   │   ├── engine.py          # ReconciliationEngine
│   │   └── reports.py         # Report generators
│   │
│   ├── analytics/             # Analytics & reports
│   │   ├── __init__.py
│   │   ├── aggregators.py
│   │   └── exporters.py
│   │
│   └── api/                   # Extended API
│       ├── __init__.py
│       ├── routes.py          # Additional endpoints
│       └── middlewares.py     # Auth, rate limiting
│
├── app.py                     # Full Flask application
├── templates/                 # Full UI templates
├── static/                    # JS, CSS assets
│
├── database/
│   ├── schema-postgresql.sql
│   └── schema-mysql.sql
│
├── tests/
└── docker/
```

---

## 5. API Design

### 5.1 FREE Version API (Read-Only)

```yaml
openapi: 3.0.0
info:
  title: E-Claim Downloader Core API
  version: 1.0.0
  description: Free download management API

paths:
  # ════════════════════════════════════════════════════════════
  # DOWNLOAD OPERATIONS
  # ════════════════════════════════════════════════════════════

  /api/v1/download/rep:
    post:
      summary: Download REP files (OP/IP/ORF)
      tags: [Download]
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                month:
                  type: integer
                  description: Month (1-12)
                year:
                  type: integer
                  description: Year in Buddhist Era (e.g., 2569)
                schemes:
                  type: array
                  items:
                    type: string
                    enum: [ucs, ofc, sss, lgo, nhs, bkk, bmt, srt]
                  default: [ucs]
              required: [month, year]
      responses:
        '200':
          description: Download started
          content:
            application/json:
              schema:
                type: object
                properties:
                  success: { type: boolean }
                  task_id: { type: string }
                  message: { type: string }
        '400':
          description: Invalid parameters

  /api/v1/download/stm:
    post:
      summary: Download STM Statement files
      tags: [Download]
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                fiscal_year:
                  type: integer
                  description: Fiscal year in Buddhist Era
                schemes:
                  type: array
                  items:
                    type: string
                    enum: [ucs, ofc, sss, lgo]
                person_type:
                  type: string
                  enum: [IP, OP, All]
                  default: All

  /api/v1/download/smt:
    post:
      summary: Fetch SMT Budget data
      tags: [Download]
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                vendor_id:
                  type: string
                  description: Hospital vendor ID (10-digit)
                start_date:
                  type: string
                  format: date
                end_date:
                  type: string
                  format: date

  /api/v1/download/bulk:
    post:
      summary: Bulk download across date range
      tags: [Download]
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                start_month: { type: integer }
                start_year: { type: integer }
                end_month: { type: integer }
                end_year: { type: integer }
                schemes: { type: array, items: { type: string } }
                download_types:
                  type: array
                  items:
                    type: string
                    enum: [rep, stm]

  # ════════════════════════════════════════════════════════════
  # STATUS & PROGRESS
  # ════════════════════════════════════════════════════════════

  /api/v1/download/status:
    get:
      summary: Get download status
      tags: [Status]
      responses:
        '200':
          content:
            application/json:
              schema:
                type: object
                properties:
                  is_running: { type: boolean }
                  current_task: { type: string, nullable: true }
                  progress:
                    type: object
                    properties:
                      downloaded: { type: integer }
                      total: { type: integer }
                      current_file: { type: string }

  /api/v1/download/progress/{task_id}:
    get:
      summary: Get task progress
      tags: [Status]
      parameters:
        - name: task_id
          in: path
          required: true
          schema: { type: string }

  # ════════════════════════════════════════════════════════════
  # HISTORY & FILES
  # ════════════════════════════════════════════════════════════

  /api/v1/history:
    get:
      summary: Get download history
      tags: [History]
      parameters:
        - name: type
          in: query
          schema:
            type: string
            enum: [rep, stm, smt, all]
          default: all
        - name: month
          in: query
          schema: { type: integer }
        - name: year
          in: query
          schema: { type: integer }
        - name: scheme
          in: query
          schema: { type: string }
        - name: page
          in: query
          schema: { type: integer, default: 1 }
        - name: per_page
          in: query
          schema: { type: integer, default: 50 }
      responses:
        '200':
          content:
            application/json:
              schema:
                type: object
                properties:
                  items:
                    type: array
                    items:
                      $ref: '#/components/schemas/DownloadRecord'
                  total: { type: integer }
                  page: { type: integer }
                  per_page: { type: integer }

  /api/v1/history/statistics:
    get:
      summary: Get download statistics
      tags: [History]
      parameters:
        - name: type
          in: query
          schema:
            type: string
            enum: [rep, stm, all]
      responses:
        '200':
          content:
            application/json:
              schema:
                type: object
                properties:
                  total_files: { type: integer }
                  total_size_bytes: { type: integer }
                  total_size_formatted: { type: string }
                  last_download: { type: string, format: date-time }
                  by_type:
                    type: object
                    additionalProperties:
                      type: integer
                  by_scheme:
                    type: object
                    additionalProperties:
                      type: integer
                  by_month:
                    type: array
                    items:
                      type: object
                      properties:
                        month: { type: integer }
                        year: { type: integer }
                        count: { type: integer }

  /api/v1/files:
    get:
      summary: List downloaded files
      tags: [Files]
      parameters:
        - name: type
          in: query
          schema:
            type: string
            enum: [rep, stm, all]
        - name: sort
          in: query
          schema:
            type: string
            enum: [date_desc, date_asc, name, size]
          default: date_desc

  /api/v1/files/{filename}:
    get:
      summary: Get file details
      tags: [Files]
    delete:
      summary: Delete file
      tags: [Files]

  /api/v1/files/{filename}/download:
    get:
      summary: Download file
      tags: [Files]
      responses:
        '200':
          description: File stream
          content:
            application/vnd.ms-excel: {}

  # ════════════════════════════════════════════════════════════
  # LOGS (SSE)
  # ════════════════════════════════════════════════════════════

  /api/v1/logs/stream:
    get:
      summary: Stream logs via Server-Sent Events
      tags: [Logs]
      responses:
        '200':
          description: SSE stream
          content:
            text/event-stream: {}

  /api/v1/logs/recent:
    get:
      summary: Get recent logs
      tags: [Logs]
      parameters:
        - name: lines
          in: query
          schema: { type: integer, default: 100 }
        - name: level
          in: query
          schema:
            type: string
            enum: [info, warning, error, all]

  # ════════════════════════════════════════════════════════════
  # CONFIGURATION
  # ════════════════════════════════════════════════════════════

  /api/v1/config:
    get:
      summary: Get configuration (no passwords)
      tags: [Config]
    patch:
      summary: Update configuration
      tags: [Config]

  /api/v1/config/test-connection:
    post:
      summary: Test NHSO connection
      tags: [Config]

components:
  schemas:
    DownloadRecord:
      type: object
      properties:
        filename: { type: string }
        download_date: { type: string, format: date-time }
        file_path: { type: string }
        file_size: { type: integer }
        file_type: { type: string, enum: [OP, IP, ORF, STM, SMT] }
        month: { type: integer }
        year: { type: integer }
        scheme: { type: string }
        url: { type: string }
```

### 5.2 PAID Version API (Extended)

```yaml
# Extends FREE API with additional endpoints

paths:
  # ════════════════════════════════════════════════════════════
  # IMPORT OPERATIONS (PRO ONLY)
  # ════════════════════════════════════════════════════════════

  /api/v1/import/rep/{filename}:
    post:
      summary: Import REP file to database
      tags: [Import, Pro]
      parameters:
        - name: filename
          in: path
          required: true
          schema: { type: string }
      responses:
        '200':
          content:
            application/json:
              schema:
                type: object
                properties:
                  success: { type: boolean }
                  imported_records: { type: integer }
                  total_records: { type: integer }
                  file_id: { type: integer }

  /api/v1/import/rep/all:
    post:
      summary: Import all pending REP files
      tags: [Import, Pro]

  /api/v1/import/stm/{filename}:
    post:
      summary: Import STM file to database
      tags: [Import, Pro]

  /api/v1/import/stm/all:
    post:
      summary: Import all pending STM files
      tags: [Import, Pro]

  /api/v1/import/status:
    get:
      summary: Get import status
      tags: [Import, Pro]

  /api/v1/import/history:
    get:
      summary: Get import history from database
      tags: [Import, Pro]

  # ════════════════════════════════════════════════════════════
  # SCHEDULER (PRO ONLY)
  # ════════════════════════════════════════════════════════════

  /api/v1/scheduler/jobs:
    get:
      summary: List scheduled jobs
      tags: [Scheduler, Pro]
    post:
      summary: Create scheduled job
      tags: [Scheduler, Pro]
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                job_type:
                  type: string
                  enum: [rep_download, stm_download, smt_fetch]
                schedule:
                  type: object
                  properties:
                    hour: { type: integer }
                    minute: { type: integer }
                    days: { type: array, items: { type: string } }
                auto_import: { type: boolean }
                schemes: { type: array, items: { type: string } }

  /api/v1/scheduler/jobs/{job_id}:
    get:
      summary: Get job details
      tags: [Scheduler, Pro]
    put:
      summary: Update job
      tags: [Scheduler, Pro]
    delete:
      summary: Delete job
      tags: [Scheduler, Pro]

  /api/v1/scheduler/jobs/{job_id}/run:
    post:
      summary: Run job immediately
      tags: [Scheduler, Pro]

  # ════════════════════════════════════════════════════════════
  # RECONCILIATION (PRO ONLY)
  # ════════════════════════════════════════════════════════════

  /api/v1/reconciliation/summary:
    get:
      summary: Get reconciliation summary
      tags: [Reconciliation, Pro]
      parameters:
        - name: fiscal_year
          in: query
          schema: { type: integer }

  /api/v1/reconciliation/monthly:
    get:
      summary: Monthly reconciliation report
      tags: [Reconciliation, Pro]
      parameters:
        - name: month
          in: query
          schema: { type: integer }
        - name: year
          in: query
          schema: { type: integer }

  /api/v1/reconciliation/fund:
    get:
      summary: Fund-based reconciliation
      tags: [Reconciliation, Pro]

  /api/v1/reconciliation/compare:
    get:
      summary: Compare REP vs STM
      tags: [Reconciliation, Pro]

  /api/v1/reconciliation/export:
    post:
      summary: Export reconciliation report
      tags: [Reconciliation, Pro]
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                format:
                  type: string
                  enum: [excel, pdf, csv]
                filters:
                  type: object

  # ════════════════════════════════════════════════════════════
  # ANALYTICS (PRO ONLY)
  # ════════════════════════════════════════════════════════════

  /api/v1/analytics/claims:
    get:
      summary: Claim analytics
      tags: [Analytics, Pro]
      parameters:
        - name: start_date
          in: query
          schema: { type: string, format: date }
        - name: end_date
          in: query
          schema: { type: string, format: date }
        - name: group_by
          in: query
          schema:
            type: string
            enum: [day, week, month, scheme, type]

  /api/v1/analytics/trends:
    get:
      summary: Trend analysis
      tags: [Analytics, Pro]

  /api/v1/analytics/dashboard:
    get:
      summary: Dashboard data (aggregated)
      tags: [Analytics, Pro]

  # ════════════════════════════════════════════════════════════
  # DATABASE (PRO ONLY)
  # ════════════════════════════════════════════════════════════

  /api/v1/database/status:
    get:
      summary: Database connection status
      tags: [Database, Pro]

  /api/v1/database/claims:
    get:
      summary: Query claims data
      tags: [Database, Pro]
      parameters:
        - name: tran_id
          in: query
          schema: { type: string }
        - name: hn
          in: query
          schema: { type: string }
        - name: pid
          in: query
          schema: { type: string }
        - name: date_from
          in: query
          schema: { type: string, format: date }
        - name: date_to
          in: query
          schema: { type: string, format: date }
```

---

## 6. Data Flow Diagrams

### 6.1 FREE Version Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    FREE VERSION DATA FLOW                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────┐         ┌──────────────────┐                       │
│  │   User   │────────▶│   CLI / Web UI   │                       │
│  │ (Manual) │         │  / REST API      │                       │
│  └──────────┘         └────────┬─────────┘                       │
│                                │                                  │
│                                ↓                                  │
│  ┌──────────────────────────────────────────────────────────────┐│
│  │                    DOWNLOAD LAYER                             ││
│  ├──────────────────────────────────────────────────────────────┤│
│  │                                                               ││
│  │  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐         ││
│  │  │REPDownloader│   │STMDownloader│   │ SMTFetcher  │         ││
│  │  └──────┬──────┘   └──────┬──────┘   └──────┬──────┘         ││
│  │         │                 │                 │                 ││
│  │         │   ┌─────────────┴─────────────┐   │                 ││
│  │         │   │     HistoryManager        │   │                 ││
│  │         │   │  (download_history.json)  │   │                 ││
│  │         │   │  (stm_download_history)   │   │                 ││
│  │         │   └─────────────┬─────────────┘   │                 ││
│  │         │                 │                 │                 ││
│  │         └────────────────┼────────────────┘                  ││
│  │                          ↓                                    ││
│  │  ┌──────────────────────────────────────────────────────────┐││
│  │  │                  downloads/ directory                     │││
│  │  │  ├─ eclaim_*.xls (REP files)                              │││
│  │  │  ├─ STM_*.xls (Statement files)                           │││
│  │  │  └─ exports/smt_*.csv (SMT exports)                       │││
│  │  └──────────────────────────────────────────────────────────┘││
│  └──────────────────────────────────────────────────────────────┘│
│                                                                   │
│  OUTPUT: Downloaded files + History JSON (NO DATABASE)           │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 PAID Version Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                     PAID VERSION DATA FLOW                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────┐   ┌──────────┐   ┌──────────────────┐              │
│  │   User   │   │ Scheduler│   │    REST API      │              │
│  │ (Manual) │   │ (Auto)   │   │   (External)     │              │
│  └────┬─────┘   └────┬─────┘   └────────┬─────────┘              │
│       │              │                  │                        │
│       └──────────────┼──────────────────┘                        │
│                      │                                           │
│                      ↓                                           │
│  ┌──────────────────────────────────────────────────────────────┐│
│  │               DOWNLOAD LAYER (from FREE)                      ││
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐             ││
│  │  │REPDownloader│ │STMDownloader│ │ SMTFetcher  │             ││
│  │  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘             ││
│  └─────────┼───────────────┼───────────────┼────────────────────┘│
│            │               │               │                     │
│            └───────────────┼───────────────┘                     │
│                            ↓                                     │
│  ┌──────────────────────────────────────────────────────────────┐│
│  │                    IMPORT LAYER (PRO)                         ││
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐             ││
│  │  │ REPImporter │ │ STMImporter │ │ SMTImporter │             ││
│  │  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘             ││
│  └─────────┼───────────────┼───────────────┼────────────────────┘│
│            │               │               │                     │
│            └───────────────┼───────────────┘                     │
│                            ↓                                     │
│  ┌──────────────────────────────────────────────────────────────┐│
│  │                    DATABASE LAYER                             ││
│  │  ┌──────────────────────────────────────────────────────────┐││
│  │  │  PostgreSQL / MySQL                                       │││
│  │  │  ├─ eclaim_imported_files     ├─ stm_imported_files      │││
│  │  │  ├─ claim_rep_opip_nhso_item  ├─ stm_claim_items         │││
│  │  │  ├─ claim_rep_orf_nhso_item   └─ smt_budget_items        │││
│  │  │  └─ health_offices                                        │││
│  │  └──────────────────────────────────────────────────────────┘││
│  └──────────────────────────────────────────────────────────────┘│
│                            │                                     │
│                            ↓                                     │
│  ┌──────────────────────────────────────────────────────────────┐│
│  │               ANALYTICS & REPORTING LAYER                     ││
│  │  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐     ││
│  │  │ Reconciliation│  │   Analytics   │  │   Dashboard   │     ││
│  │  │    Engine     │  │   Reports     │  │   Metrics     │     ││
│  │  └───────────────┘  └───────────────┘  └───────────────┘     ││
│  └──────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

---

## 7. Class Design

### 7.1 Core Classes (FREE Version)

```python
# ════════════════════════════════════════════════════════════════
# BASE DOWNLOADER (Abstract)
# ════════════════════════════════════════════════════════════════

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from enum import Enum
import requests

class DownloadType(Enum):
    REP = "rep"
    STM = "stm"
    SMT = "smt"

class FileType(Enum):
    OP = "OP"
    IP = "IP"
    ORF = "ORF"
    IP_APPEAL = "IP_APPEAL"
    IP_APPEAL_NHSO = "IP_APPEAL_NHSO"

class Scheme(Enum):
    UCS = "ucs"
    OFC = "ofc"
    SSS = "sss"
    LGO = "lgo"
    NHS = "nhs"
    BKK = "bkk"
    BMT = "bmt"
    SRT = "srt"

@dataclass
class DownloadResult:
    """Result of a download operation"""
    success: bool
    filename: str
    file_path: str
    file_size: int
    download_type: DownloadType
    file_type: Optional[FileType]
    scheme: Optional[Scheme]
    month: Optional[int]
    year: Optional[int]
    error: Optional[str] = None
    metadata: Dict[str, Any] = None

@dataclass
class DownloadProgress:
    """Progress tracking for downloads"""
    total: int
    downloaded: int
    skipped: int
    errors: int
    current_file: Optional[str]
    is_running: bool

class BaseDownloader(ABC):
    """
    Abstract base class for all downloaders.
    Provides common functionality for authentication, session management,
    and progress tracking.
    """

    def __init__(
        self,
        download_dir: str = "./downloads",
        history_manager: Optional['HistoryManager'] = None,
        logger: Optional['LogStreamer'] = None
    ):
        self.download_dir = download_dir
        self.history = history_manager or HistoryManager()
        self.logger = logger or LogStreamer()
        self.session: Optional[requests.Session] = None
        self._progress = DownloadProgress(0, 0, 0, 0, None, False)

    @property
    @abstractmethod
    def download_type(self) -> DownloadType:
        """Return the type of downloader"""
        pass

    @abstractmethod
    def login(self, username: str, password: str) -> bool:
        """Authenticate with the remote system"""
        pass

    @abstractmethod
    def get_download_links(self, **kwargs) -> List[Dict[str, Any]]:
        """Get list of available downloads"""
        pass

    @abstractmethod
    def download_file(self, url: str, filename: str) -> DownloadResult:
        """Download a single file"""
        pass

    def download_all(self, links: List[Dict]) -> List[DownloadResult]:
        """Download all files from links"""
        results = []
        self._progress.total = len(links)
        self._progress.is_running = True

        for link in links:
            self._progress.current_file = link.get('filename')
            result = self.download_file(link['url'], link['filename'])
            results.append(result)

            if result.success:
                self._progress.downloaded += 1
                self.history.add_record(result)
            elif result.error == "skipped":
                self._progress.skipped += 1
            else:
                self._progress.errors += 1

        self._progress.is_running = False
        return results

    @property
    def progress(self) -> DownloadProgress:
        return self._progress


# ════════════════════════════════════════════════════════════════
# REP DOWNLOADER
# ════════════════════════════════════════════════════════════════

class REPDownloader(BaseDownloader):
    """
    Downloads REP (Representative) files from NHSO E-Claim portal.
    Supports OP, IP, and ORF file types.
    """

    BASE_URL = "https://eclaim.nhso.go.th"
    LOGIN_URL = f"{BASE_URL}/webComponent/mainloginAction.do"

    def __init__(
        self,
        month: Optional[int] = None,
        year: Optional[int] = None,  # Buddhist Era
        schemes: List[Scheme] = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.month = month or self._current_be_month()
        self.year = year or self._current_be_year()
        self.schemes = schemes or [Scheme.UCS]

    @property
    def download_type(self) -> DownloadType:
        return DownloadType.REP

    def login(self, username: str, password: str) -> bool:
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 Chrome/120.0.0.0',
            'Accept-Language': 'th-TH,th;q=0.9,en;q=0.8'
        })

        # Get login page for cookies
        self.session.get(self.LOGIN_URL)

        # Submit login
        response = self.session.post(self.LOGIN_URL, data={
            'user': username,
            'pass': password
        })

        # Check if login successful
        if 'login' in response.url and 'error' in response.text.lower():
            self.logger.write("Login failed", level='error', source='rep_download')
            return False

        self.logger.write("Login successful", level='success', source='rep_download')
        return True

    def get_download_links(self, file_type: FileType = None) -> List[Dict]:
        """Get download links for specified month/year/schemes"""
        links = []

        for scheme in self.schemes:
            url = self._build_validation_url(scheme)
            response = self.session.get(url)

            # Parse HTML for download links
            parsed_links = self._parse_download_links(response.text, scheme)
            links.extend(parsed_links)

        return links

    def download_file(self, url: str, filename: str) -> DownloadResult:
        """Download single REP file"""
        file_path = os.path.join(self.download_dir, filename)

        # Check if already downloaded
        if self.history.exists(filename):
            return DownloadResult(
                success=False,
                filename=filename,
                file_path=file_path,
                file_size=0,
                download_type=self.download_type,
                file_type=self._detect_file_type(filename),
                scheme=self._detect_scheme(filename),
                month=self.month,
                year=self.year,
                error="skipped"
            )

        # Download with retry
        for attempt in range(3):
            try:
                response = self.session.get(url, stream=True)
                response.raise_for_status()

                with open(file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)

                file_size = os.path.getsize(file_path)

                if file_size < 100:
                    raise ValueError("File too small, likely error")

                self.logger.write(
                    f"Downloaded: {filename} ({file_size} bytes)",
                    level='success',
                    source='rep_download'
                )

                return DownloadResult(
                    success=True,
                    filename=filename,
                    file_path=file_path,
                    file_size=file_size,
                    download_type=self.download_type,
                    file_type=self._detect_file_type(filename),
                    scheme=self._detect_scheme(filename),
                    month=self.month,
                    year=self.year
                )

            except Exception as e:
                self.logger.write(
                    f"Attempt {attempt+1} failed: {str(e)}",
                    level='warning',
                    source='rep_download'
                )
                time.sleep(2)

        return DownloadResult(
            success=False,
            filename=filename,
            file_path=file_path,
            file_size=0,
            download_type=self.download_type,
            file_type=None,
            scheme=None,
            month=self.month,
            year=self.year,
            error="Max retries exceeded"
        )


# ════════════════════════════════════════════════════════════════
# STM DOWNLOADER
# ════════════════════════════════════════════════════════════════

class STMDownloader(BaseDownloader):
    """
    Downloads STM (Statement) files from NHSO.
    Similar to REP but for payment statements.
    """

    SCHEME_URLS = {
        Scheme.UCS: "/webComponent/ucs/statementUCSAction.do",
        Scheme.OFC: "/webComponent/ofc/statementOFCAction.do",
        Scheme.SSS: "/webComponent/sss/statementSSSAction.do",
        Scheme.LGO: "/webComponent/lgo/statementLGOAction.do",
    }

    @property
    def download_type(self) -> DownloadType:
        return DownloadType.STM

    # ... similar implementation to REPDownloader


# ════════════════════════════════════════════════════════════════
# SMT FETCHER (No auth required)
# ════════════════════════════════════════════════════════════════

class SMTFetcher(BaseDownloader):
    """
    Fetches budget data from SMT (Smart Money Transfer) API.
    Public API - no authentication required.
    """

    API_URL = "https://smt.nhso.go.th/smtf/api/budgetreport/budgetSummaryByVendorReport/search"

    def __init__(self, vendor_id: str, **kwargs):
        super().__init__(**kwargs)
        self.vendor_id = vendor_id.zfill(10)  # Pad to 10 digits

    @property
    def download_type(self) -> DownloadType:
        return DownloadType.SMT

    def login(self, username: str = None, password: str = None) -> bool:
        """SMT API is public, no login needed"""
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        return True

    def fetch_budget(
        self,
        start_date: str,  # dd/mm/yyyy BE
        end_date: str,
        budget_source: str = "02"
    ) -> Dict[str, Any]:
        """Fetch budget summary data"""
        payload = {
            "budgetYear": "",
            "startDate": start_date,
            "endDate": end_date,
            "budgetSource": budget_source,
            "vendorSearchCondition": self.vendor_id
        }

        response = self.session.post(self.API_URL, json=payload)
        response.raise_for_status()

        return response.json()


# ════════════════════════════════════════════════════════════════
# HISTORY MANAGER
# ════════════════════════════════════════════════════════════════

class HistoryManager:
    """
    Manages download history using JSON files.
    Thread-safe with atomic writes.
    """

    def __init__(
        self,
        rep_file: str = "download_history.json",
        stm_file: str = "stm_download_history.json"
    ):
        self.rep_file = rep_file
        self.stm_file = stm_file
        self._lock = threading.Lock()

    def add_record(self, result: DownloadResult) -> None:
        """Add download record to history"""
        with self._lock:
            history = self._load(result.download_type)

            record = {
                "filename": result.filename,
                "download_date": datetime.now().isoformat(),
                "file_path": result.file_path,
                "file_size": result.file_size,
                "file_type": result.file_type.value if result.file_type else None,
                "scheme": result.scheme.value if result.scheme else None,
                "month": result.month,
                "year": result.year,
                "url": result.metadata.get('url') if result.metadata else None
            }

            history.setdefault('downloads', []).append(record)
            history['last_run'] = datetime.now().isoformat()

            self._save(result.download_type, history)

    def exists(self, filename: str) -> bool:
        """Check if file already downloaded"""
        for dtype in [DownloadType.REP, DownloadType.STM]:
            history = self._load(dtype)
            for record in history.get('downloads', []):
                if record['filename'] == filename:
                    return True
        return False

    def get_statistics(self, download_type: DownloadType = None) -> Dict:
        """Get download statistics"""
        # ... statistics calculation

    def _load(self, download_type: DownloadType) -> Dict:
        """Load history file"""
        filename = self.rep_file if download_type == DownloadType.REP else self.stm_file
        try:
            with open(filename, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {'downloads': [], 'last_run': None}

    def _save(self, download_type: DownloadType, data: Dict) -> None:
        """Atomic save with backup"""
        filename = self.rep_file if download_type == DownloadType.REP else self.stm_file

        # Create backup
        if os.path.exists(filename):
            shutil.copy(filename, f"{filename}.backup")

        # Write to temp file
        temp_file = f"{filename}.tmp"
        with open(temp_file, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        # Atomic rename
        os.replace(temp_file, filename)


# ════════════════════════════════════════════════════════════════
# LOG STREAMER
# ════════════════════════════════════════════════════════════════

class LogStreamer:
    """
    Real-time logging with JSON format.
    Supports SSE streaming for web UI.
    """

    def __init__(self, log_file: str = "logs/realtime.log"):
        self.log_file = log_file
        self._lock = threading.Lock()

    def write(
        self,
        message: str,
        level: str = 'info',
        source: str = 'system'
    ) -> None:
        """Write log entry"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "source": source,
            "message": message
        }

        with self._lock:
            with open(self.log_file, 'a') as f:
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')

    def stream(self, tail: int = 100):
        """Generator for SSE streaming"""
        # Read last N lines
        with open(self.log_file, 'r') as f:
            lines = f.readlines()[-tail:]
            for line in lines:
                yield f"data: {line}\n\n"

        # Stream new lines
        with open(self.log_file, 'r') as f:
            f.seek(0, 2)  # End of file
            while True:
                line = f.readline()
                if line:
                    yield f"data: {line}\n\n"
                else:
                    time.sleep(0.5)
```

### 7.2 Pro Classes (PAID Version)

```python
# ════════════════════════════════════════════════════════════════
# BASE IMPORTER (PRO)
# ════════════════════════════════════════════════════════════════

from abc import ABC, abstractmethod
from typing import Generator
import pandas as pd

@dataclass
class ImportResult:
    """Result of import operation"""
    success: bool
    file_id: int
    filename: str
    imported_records: int
    total_records: int
    skipped_records: int
    error_records: int
    errors: List[str]
    duration_seconds: float

class BaseImporter(ABC):
    """
    Abstract base class for database importers.
    Handles batch processing, error handling, and progress tracking.
    """

    def __init__(
        self,
        db_connection: 'DatabaseConnection',
        batch_size: int = 100,
        logger: Optional['LogStreamer'] = None
    ):
        self.db = db_connection
        self.batch_size = batch_size
        self.logger = logger or LogStreamer()

    @abstractmethod
    def get_column_mapping(self) -> Dict[str, str]:
        """Return Excel column → DB column mapping"""
        pass

    @abstractmethod
    def get_table_name(self) -> str:
        """Return target database table name"""
        pass

    def import_file(self, file_path: str) -> ImportResult:
        """Import file to database"""
        start_time = time.time()

        # Create import record
        file_id = self._create_import_record(file_path)

        try:
            # Parse Excel file
            df = self._parse_file(file_path)
            total_records = len(df)

            # Import in batches
            imported = 0
            errors = []

            for batch_df in self._batch_generator(df):
                batch_result = self._import_batch(file_id, batch_df)
                imported += batch_result['imported']
                errors.extend(batch_result.get('errors', []))

            # Update import record
            self._complete_import_record(file_id, imported, total_records)

            return ImportResult(
                success=True,
                file_id=file_id,
                filename=os.path.basename(file_path),
                imported_records=imported,
                total_records=total_records,
                skipped_records=0,
                error_records=len(errors),
                errors=errors,
                duration_seconds=time.time() - start_time
            )

        except Exception as e:
            self._fail_import_record(file_id, str(e))
            raise

    def _batch_generator(self, df: pd.DataFrame) -> Generator[pd.DataFrame, None, None]:
        """Yield DataFrames in batches"""
        for i in range(0, len(df), self.batch_size):
            yield df.iloc[i:i + self.batch_size]


# ════════════════════════════════════════════════════════════════
# REP IMPORTER (PRO)
# ════════════════════════════════════════════════════════════════

class REPImporter(BaseImporter):
    """
    Imports REP (OP/IP) files to claim_rep_opip_nhso_item table.
    Handles Thai dates, column mapping, and UPSERT logic.
    """

    COLUMN_MAPPING = {
        'TRAN_ID': 'tran_id',
        'REPNO': 'repno',
        'HN': 'hn',
        'PID': 'pid',
        'VISITDATE': 'visitdate',
        # ... full 49-column mapping
    }

    def get_column_mapping(self) -> Dict[str, str]:
        return self.COLUMN_MAPPING

    def get_table_name(self) -> str:
        return 'claim_rep_opip_nhso_item'

    def _import_batch(self, file_id: int, df: pd.DataFrame) -> Dict:
        """Import batch with UPSERT"""
        # Map columns
        mapped_df = self._map_columns(df)

        # Add file_id
        mapped_df['file_id'] = file_id

        # Build UPSERT query
        columns = list(mapped_df.columns)
        placeholders = ', '.join(['%s'] * len(columns))

        if self.db.db_type == 'postgresql':
            query = f"""
                INSERT INTO {self.get_table_name()} ({', '.join(columns)})
                VALUES ({placeholders})
                ON CONFLICT (tran_id, file_id) DO UPDATE SET
                {', '.join(f'{col} = EXCLUDED.{col}' for col in columns if col not in ['tran_id', 'file_id'])}
            """
        else:  # MySQL
            query = f"""
                INSERT INTO {self.get_table_name()} ({', '.join(columns)})
                VALUES ({placeholders})
                ON DUPLICATE KEY UPDATE
                {', '.join(f'{col} = VALUES({col})' for col in columns if col not in ['tran_id', 'file_id'])}
            """

        # Execute batch
        imported = 0
        errors = []

        for _, row in mapped_df.iterrows():
            try:
                self.db.execute(query, tuple(row.values))
                imported += 1
            except Exception as e:
                errors.append(f"Row {row.get('tran_id')}: {str(e)}")

        self.db.commit()

        return {'imported': imported, 'errors': errors}


# ════════════════════════════════════════════════════════════════
# SCHEDULER MANAGER (PRO)
# ════════════════════════════════════════════════════════════════

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

@dataclass
class ScheduledJob:
    """Scheduled job configuration"""
    job_id: str
    job_type: str  # rep_download, stm_download, smt_fetch
    hour: int
    minute: int
    enabled: bool
    auto_import: bool
    schemes: List[str]
    next_run: Optional[datetime]

class SchedulerManager:
    """
    Manages scheduled download and import jobs.
    Uses APScheduler with CronTrigger.
    """

    def __init__(self, settings: 'SettingsManager'):
        self.settings = settings
        self.scheduler = BackgroundScheduler(timezone='Asia/Bangkok')
        self._jobs: Dict[str, ScheduledJob] = {}

    def start(self):
        """Start scheduler and load saved jobs"""
        self.scheduler.start()
        self._load_jobs_from_settings()

    def add_job(
        self,
        job_type: str,
        hour: int,
        minute: int,
        auto_import: bool = False,
        schemes: List[str] = None
    ) -> ScheduledJob:
        """Add new scheduled job"""
        job_id = f"{job_type}_{hour:02d}_{minute:02d}"

        # Remove existing if any
        if job_id in self._jobs:
            self.scheduler.remove_job(job_id)

        # Add to APScheduler
        self.scheduler.add_job(
            self._execute_job,
            CronTrigger(hour=hour, minute=minute),
            id=job_id,
            args=[job_type, auto_import, schemes]
        )

        # Track job
        job = ScheduledJob(
            job_id=job_id,
            job_type=job_type,
            hour=hour,
            minute=minute,
            enabled=True,
            auto_import=auto_import,
            schemes=schemes or ['ucs'],
            next_run=self._get_next_run(job_id)
        )
        self._jobs[job_id] = job

        # Save to settings
        self._save_jobs_to_settings()

        return job

    def _execute_job(self, job_type: str, auto_import: bool, schemes: List[str]):
        """Execute scheduled job"""
        if job_type == 'rep_download':
            # Run REP downloader subprocess
            subprocess.Popen([
                sys.executable,
                'cli/download_rep.py',
                '--schemes', ','.join(schemes),
                '--auto-import' if auto_import else ''
            ])
        elif job_type == 'stm_download':
            # Run STM downloader
            pass
        elif job_type == 'smt_fetch':
            # Run SMT fetcher
            pass


# ════════════════════════════════════════════════════════════════
# RECONCILIATION ENGINE (PRO)
# ════════════════════════════════════════════════════════════════

@dataclass
class ReconciliationResult:
    """Reconciliation comparison result"""
    period: str  # YYYY-MM
    rep_total: Decimal
    stm_total: Decimal
    difference: Decimal
    difference_percent: float
    matched_count: int
    unmatched_count: int
    details: List[Dict]

class ReconciliationEngine:
    """
    Compares REP (claims) vs STM (payments) data.
    Identifies discrepancies and generates reports.
    """

    def __init__(self, db: 'DatabaseConnection'):
        self.db = db

    def reconcile_monthly(
        self,
        month: int,
        year: int,  # Gregorian
        scheme: str = None
    ) -> ReconciliationResult:
        """Reconcile REP vs STM for specific month"""

        # Query REP totals
        rep_query = """
            SELECT
                COUNT(*) as claim_count,
                SUM(paid_amount) as total_paid,
                SUM(claim_amount) as total_claimed
            FROM claim_rep_opip_nhso_item
            WHERE EXTRACT(MONTH FROM dateadm) = %s
              AND EXTRACT(YEAR FROM dateadm) = %s
        """
        if scheme:
            rep_query += f" AND scheme = '{scheme}'"

        rep_result = self.db.fetch_one(rep_query, (month, year))

        # Query STM totals
        stm_query = """
            SELECT
                COUNT(*) as item_count,
                SUM(amount) as total_amount
            FROM stm_claim_items
            WHERE EXTRACT(MONTH FROM statement_date) = %s
              AND EXTRACT(YEAR FROM statement_date) = %s
        """
        if scheme:
            stm_query += f" AND scheme = '{scheme}'"

        stm_result = self.db.fetch_one(stm_query, (month, year))

        # Calculate differences
        rep_total = Decimal(rep_result['total_paid'] or 0)
        stm_total = Decimal(stm_result['total_amount'] or 0)
        difference = rep_total - stm_total

        return ReconciliationResult(
            period=f"{year}-{month:02d}",
            rep_total=rep_total,
            stm_total=stm_total,
            difference=difference,
            difference_percent=float(difference / rep_total * 100) if rep_total else 0,
            matched_count=0,  # Detailed matching TBD
            unmatched_count=0,
            details=[]
        )

    def generate_report(
        self,
        fiscal_year: int,
        format: str = 'excel'
    ) -> bytes:
        """Generate reconciliation report"""
        # ... report generation
```

---

## 8. Migration Plan

### 8.1 Phase 1: Code Extraction (Week 1-2)

```
┌─────────────────────────────────────────────────────────────────┐
│                    PHASE 1: CODE EXTRACTION                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Step 1: Create new repo structure                               │
│  ═══════════════════════════════════                              │
│  $ mkdir eclaim-downloader-core                                  │
│  $ cd eclaim-downloader-core                                     │
│  $ git init                                                      │
│  $ mkdir -p eclaim_core/{downloaders,auth,history,logging,config}│
│                                                                   │
│  Step 2: Extract download components                             │
│  ════════════════════════════════════                             │
│  Copy and refactor:                                              │
│  - eclaim_downloader_http.py → eclaim_core/downloaders/rep.py   │
│  - stm_downloader_http.py → eclaim_core/downloaders/stm.py      │
│  - smt_budget_fetcher.py → eclaim_core/downloaders/smt.py       │
│  - utils/history_manager.py → eclaim_core/history/manager.py    │
│  - utils/log_stream.py → eclaim_core/logging/streamer.py        │
│  - utils/settings_manager.py → eclaim_core/config/settings.py   │
│                                                                   │
│  Step 3: Create abstract base classes                            │
│  ═════════════════════════════════════                            │
│  - BaseDownloader with common interface                          │
│  - DownloadResult, DownloadProgress dataclasses                  │
│  - Scheme, FileType, DownloadType enums                          │
│                                                                   │
│  Step 4: Write CLI tools                                         │
│  ════════════════════════════                                     │
│  - cli/download_rep.py (argparse wrapper)                        │
│  - cli/download_stm.py                                           │
│  - cli/fetch_smt.py                                              │
│  - cli/bulk_download.py                                          │
└─────────────────────────────────────────────────────────────────┘
```

### 8.2 Phase 2: API Development (Week 2-3)

```
┌─────────────────────────────────────────────────────────────────┐
│                    PHASE 2: API DEVELOPMENT                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Step 1: Create Flask Blueprint                                  │
│  ═══════════════════════════════                                  │
│  eclaim_core/api/                                                │
│  ├─ __init__.py (create_blueprint function)                      │
│  ├─ routes.py                                                    │
│  │   ├─ /api/v1/download/rep                                     │
│  │   ├─ /api/v1/download/stm                                     │
│  │   ├─ /api/v1/download/smt                                     │
│  │   ├─ /api/v1/download/status                                  │
│  │   ├─ /api/v1/history                                          │
│  │   ├─ /api/v1/files                                            │
│  │   └─ /api/v1/logs/stream                                      │
│  └─ schemas.py (Pydantic/Marshmallow models)                     │
│                                                                   │
│  Step 2: Create minimal web app                                  │
│  ═══════════════════════════════                                  │
│  web/                                                            │
│  ├─ app.py                                                       │
│  │   from eclaim_core.api import create_blueprint                │
│  │   app.register_blueprint(create_blueprint(), url_prefix='/') │
│  ├─ templates/ (simplified UI)                                   │
│  └─ static/                                                      │
│                                                                   │
│  Step 3: Write tests                                             │
│  ═══════════════════                                              │
│  tests/                                                          │
│  ├─ test_downloaders.py                                          │
│  ├─ test_api.py                                                  │
│  └─ test_history.py                                              │
└─────────────────────────────────────────────────────────────────┘
```

### 8.3 Phase 3: Pro Integration (Week 3-4)

```
┌─────────────────────────────────────────────────────────────────┐
│                   PHASE 3: PRO INTEGRATION                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Step 1: Add core as submodule                                   │
│  ════════════════════════════════                                 │
│  cd eclaim-platform-pro                                          │
│  git submodule add https://github.com/.../core.git lib/core     │
│                                                                   │
│  Step 2: Update imports in pro code                              │
│  ═══════════════════════════════════                              │
│  # Before                                                        │
│  from eclaim_downloader_http import EClaimDownloader            │
│                                                                   │
│  # After                                                         │
│  from lib.core.eclaim_core.downloaders import REPDownloader     │
│                                                                   │
│  Step 3: Refactor app.py to use core blueprint                   │
│  ═════════════════════════════════════════════                    │
│  from lib.core.eclaim_core.api import create_blueprint          │
│  from eclaim_pro.api import create_pro_blueprint                │
│                                                                   │
│  app.register_blueprint(create_blueprint(), url_prefix='/api/v1')│
│  app.register_blueprint(create_pro_blueprint(), url_prefix='/api/v1/pro')│
│                                                                   │
│  Step 4: Keep pro-only features separate                         │
│  ════════════════════════════════════════                         │
│  eclaim_pro/                                                     │
│  ├─ importers/                                                   │
│  ├─ scheduler/                                                   │
│  ├─ reconciliation/                                              │
│  └─ api/ (pro endpoints only)                                    │
└─────────────────────────────────────────────────────────────────┘
```

### 8.4 Phase 4: Testing & Documentation (Week 4)

```
┌─────────────────────────────────────────────────────────────────┐
│              PHASE 4: TESTING & DOCUMENTATION                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Testing Checklist:                                              │
│  ═══════════════════                                              │
│  □ Core module works standalone (FREE version)                   │
│  □ Core module works as submodule (PRO version)                  │
│  □ All 3 download types functional                               │
│  □ History tracking correct                                      │
│  □ API endpoints respond correctly                               │
│  □ SSE log streaming works                                       │
│  □ PRO import still works                                        │
│  □ PRO scheduler still works                                     │
│  □ Docker builds work                                            │
│                                                                   │
│  Documentation:                                                  │
│  ══════════════                                                   │
│  □ README.md for core                                            │
│  □ API documentation (OpenAPI/Swagger)                           │
│  □ Installation guide                                            │
│  □ Usage examples                                                │
│  □ Migration guide for existing users                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 9. Feature Comparison

| Feature | FREE Version | PAID Version |
|---------|--------------|--------------|
| **Download** |||
| REP Download (OP/IP/ORF) | ✅ | ✅ |
| STM Download (Statement) | ✅ | ✅ |
| SMT Fetch (Budget API) | ✅ | ✅ |
| Bulk Download | ✅ | ✅ |
| Download History | ✅ | ✅ |
| Duplicate Prevention | ✅ | ✅ |
| **Web UI** |||
| View Downloaded Files | ✅ | ✅ |
| Download File | ✅ | ✅ |
| Real-time Logs | ✅ | ✅ |
| Basic Dashboard | ✅ | ✅ (Enhanced) |
| **API** |||
| Download API | ✅ | ✅ |
| History API | ✅ | ✅ |
| Status/Progress API | ✅ | ✅ |
| **Database** |||
| Database Import | ❌ | ✅ |
| UPSERT Support | ❌ | ✅ |
| PostgreSQL/MySQL | ❌ | ✅ |
| **Automation** |||
| Scheduler | ❌ | ✅ |
| Auto-import | ❌ | ✅ |
| **Analytics** |||
| Reconciliation | ❌ | ✅ |
| Reports | ❌ | ✅ |
| Claim Statistics | ❌ | ✅ |
| Fund Analysis | ❌ | ✅ |
| **Support** |||
| Community Support | ✅ | ✅ |
| Priority Support | ❌ | ✅ |
| Custom Development | ❌ | ✅ |

---

## 10. Licensing Strategy

### 10.1 FREE Version
- **License:** MIT or Apache 2.0
- **Distribution:** GitHub public repo
- **Use:** Unlimited, commercial use allowed
- **Modification:** Allowed
- **Attribution:** Required

### 10.2 PAID Version
- **License:** Commercial license
- **Distribution:** Private repo or Docker registry
- **Pricing Models:**
  - Per-hospital license
  - Subscription (monthly/yearly)
  - One-time purchase + support contract
- **Features:**
  - Source code (optional)
  - Docker image only (recommended)
  - Technical support included

---

## 11. Next Steps

1. **Approve this specification**
2. **Create eclaim-downloader-core repo**
3. **Extract and refactor code** following Phase 1
4. **Develop REST API** following Phase 2
5. **Integrate into Pro version** following Phase 3
6. **Test both versions thoroughly**
7. **Document and release**

---

## Appendix A: File Mapping (Current → New)

| Current File | FREE Repo | PAID Repo |
|--------------|-----------|-----------|
| `eclaim_downloader_http.py` | `eclaim_core/downloaders/rep.py` | via submodule |
| `stm_downloader_http.py` | `eclaim_core/downloaders/stm.py` | via submodule |
| `smt_budget_fetcher.py` | `eclaim_core/downloaders/smt.py` | via submodule |
| `bulk_downloader.py` | `cli/bulk_download.py` | via submodule |
| `utils/history_manager.py` | `eclaim_core/history/manager.py` | via submodule |
| `utils/log_stream.py` | `eclaim_core/logging/streamer.py` | via submodule |
| `utils/settings_manager.py` | `eclaim_core/config/settings.py` | via submodule |
| `utils/file_manager.py` | `eclaim_core/utils/file_manager.py` | via submodule |
| `eclaim_import.py` | N/A | `cli/import_rep.py` |
| `utils/eclaim/importer_v2.py` | N/A | `eclaim_pro/importers/rep.py` |
| `utils/scheduler.py` | N/A | `eclaim_pro/scheduler/manager.py` |
| `app.py` | `web/app.py` (minimal) | `app.py` (full) |

---

**Document Status:** Draft v1.0
**Review Required:** ✅ Architecture, API Design, Migration Plan
