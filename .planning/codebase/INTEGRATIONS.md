# External Integrations

**Analysis Date:** 2026-01-11

## APIs & External Services

**NHSO E-Claim System (Primary):**
- Purpose: Download claim validation data from National Health Security Office
- Base URL: `https://eclaim.nhso.go.th`
- Integration method: HTTP requests with session-based authentication
- Client: `requests` library (`eclaim_downloader_http.py`)
- Auth: Username/password credentials
- Data format: Excel .xls files (OP, IP, ORF, IP_APPEAL types)
- Calendar: Thai Buddhist Era (Gregorian year + 543)

**SMT Budget System (Secondary):**
- Purpose: Fetch budget/payment data for hospital
- Implementation: `smt_budget_fetcher.py`
- Auth: Vendor ID configuration

## Data Storage

**Databases:**

*PostgreSQL 15 (Primary):*
- Connection: via `DATABASE_URL` or individual `DB_*` env vars
- Client: psycopg2-binary (`config/database.py`)
- Schema: `database/schema-postgresql-merged.sql`
- Tables:
  - `eclaim_imported_files` - Import tracking
  - `claim_rep_opip_nhso_item` - OP/IP claim data
  - `claim_rep_orf_nhso_item` - ORF claim data

*MySQL (Alternative):*
- Client: pymysql
- Schema: `database/schema-mysql-merged.sql`
- Docker compose: `docker-compose-mysql.yml`

**File Storage:**
- Local filesystem only
- Downloads directory: `downloads/` (gitignored)
- Exports directory: `exports/`
- Logs directory: `logs/`

**Caching:**
- None (all database queries)

## Authentication & Identity

**NHSO Authentication:**
- Session-based HTTP login
- Credentials: `ECLAIM_USERNAME`, `ECLAIM_PASSWORD` env vars
- Fallback: `config/settings.json` (user-configured via Web UI)
- Implementation: `eclaim_downloader_http.py` lines 43-98

**Application Auth:**
- None (no user authentication for web UI)
- Flask SECRET_KEY for session management

## Monitoring & Observability

**Error Tracking:**
- None (application logs only)

**Logs:**
- Application logs to `logs/` directory
- Real-time streaming via SSE (`utils/log_stream.py`)
- Endpoint: `/logs/stream`

## CI/CD & Deployment

**Hosting:**
- Docker container deployment
- Container registry: `ghcr.io/aegisx-platform/eclaim-rep-download`
- Compose files:
  - `docker-compose.yml` - PostgreSQL (default)
  - `docker-compose-mysql.yml` - MySQL alternative
  - `docker-compose-no-db.yml` - Download-only

**CI Pipeline:**
- GitHub Actions (`.github/` directory present)
- Registry: GitHub Container Registry (ghcr.io)

## Environment Configuration

**Development:**
- Required env vars: `ECLAIM_USERNAME`, `ECLAIM_PASSWORD`, `DB_*`
- Secrets location: `.env` file (gitignored)
- Template: `.env.example`

**Production:**
- Secrets: Environment variables in Docker
- Database: PostgreSQL container or external database
- Health checks: HTTP `/dashboard` endpoint

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- None

## Real-Time Communication

**Server-Sent Events (SSE):**
- Endpoint: `/logs/stream` (`utils/log_stream.py`)
- Purpose: Real-time log streaming to web UI
- Client: EventSource in `static/js/app.js`
- Thread-safe with lock mechanism

## Data Flow

```
NHSO E-Claim System (eclaim.nhso.go.th)
    ↓ (HTTP Request with credentials)
eclaim_downloader_http.py (authentication & download)
    ↓ (Excel .xls files)
downloads/ directory (local storage)
    ↓ (File parsing)
utils/eclaim/parser.py (pandas + xlrd)
    ↓ (Data transformation)
utils/eclaim/importer_v2.py (column mapping)
    ↓ (UPSERT operations)
PostgreSQL / MySQL Database
    ├── eclaim_imported_files (metadata)
    ├── claim_rep_opip_nhso_item (claim data)
    └── claim_rep_orf_nhso_item (claim data)
    ↓ (Real-time monitoring)
Web UI (Flask + SSE)
```

## Network Configuration

**Docker DNS:**
- Explicit DNS servers configured for reliable NHSO connectivity:
  - 8.8.8.8 (Google)
  - 8.8.4.4 (Google Secondary)
  - 1.1.1.1 (Cloudflare)

**Docker Network:**
- Bridge network: `eclaim-network`
- Service-to-service communication via service names

---

*Integration audit: 2026-01-11*
*Update when adding/removing external services*
