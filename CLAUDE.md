# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

E-Claim Downloader & Data Import System - A Flask-based web application that automates downloading and importing E-Claim data from NHSO (National Health Security Office) for Thai hospitals. The system uses HTTP client-based downloads (no Playwright browser automation) and supports both PostgreSQL and MySQL databases with Schema V2 (hospital's existing structure).

## Commands

### Development

```bash
# Local development setup
python3.12 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with credentials

# Run Flask web UI
FLASK_ENV=development python app.py
# Access at http://localhost:5001

# Run downloader (single month)
python eclaim_downloader_http.py

# Run bulk downloader (date range)
python bulk_downloader.py

# Import single file
python eclaim_import.py downloads/filename.xls

# Import all files in downloads/
python eclaim_import.py downloads/
```

### Docker Deployment

**Quick Start (Using Pre-built Images):**
```bash
# Clone and setup
git clone https://github.com/aegisx-platform/eclaim-rep-download.git
cd eclaim-rep-download
cp .env.example .env
nano .env  # Set ECLAIM_USERNAME and ECLAIM_PASSWORD

# Start services (pulls pre-built image from ghcr.io)
docker-compose up -d

# View logs
docker-compose logs -f web
```

**Development Mode (Build from source):**
```bash
# Build locally
docker-compose build
docker-compose up -d

# Rebuild after code changes
docker-compose build --no-cache
docker-compose up -d
```

**Other Options:**
```bash
# MySQL instead of PostgreSQL
docker-compose -f docker-compose-mysql.yml up -d

# Download-only (no database)
docker-compose -f docker-compose-no-db.yml up -d

# Use specific version (set in .env)
VERSION=v2.0.0 docker-compose up -d

# Database shell access
docker-compose exec db psql -U eclaim -d eclaim_db  # PostgreSQL
docker-compose exec db mysql -u eclaim -p eclaim_db  # MySQL

# Container shell
docker-compose exec web bash
```

**Update to New Version:**
```bash
# Set version in .env
echo "VERSION=v2.1.0" >> .env

# Pull and restart
docker-compose pull
docker-compose up -d
```

### Testing

```bash
# Test database connection
docker-compose exec web python -c "from config.database import get_db_config; import psycopg2; conn = psycopg2.connect(**get_db_config()); print('✓ Connected')"

# Test downloader (dry run)
docker-compose exec web python eclaim_downloader_http.py

# Test importer on single file
docker-compose exec web python eclaim_import.py downloads/sample.xls

# View import logs
docker-compose logs -f web

# Check imported data
docker-compose exec db psql -U eclaim -d eclaim_db -c "SELECT COUNT(*) FROM claim_rep_opip_nhso_item;"
```

## Architecture

### Core Components

1. **Flask Web Application (`app.py`)**
   - Web UI dashboard with statistics, file management, and real-time logs
   - REST API endpoints for downloads, imports, and scheduling
   - Server-Sent Events (SSE) for real-time log streaming via `utils/log_stream.py`
   - Manager pattern: `HistoryManager`, `FileManager`, `DownloaderRunner`, `ImportRunner`, `SettingsManager`

2. **HTTP Downloader (`eclaim_downloader_http.py`)**
   - Uses `requests` library (not Playwright) for fast, lightweight downloads
   - Session-based authentication with NHSO e-claim system
   - Duplicate prevention via `download_history.json`
   - Supports single month or bulk date range downloads

3. **Database Importer (`utils/eclaim/importer_v2.py`)**
   - **Schema V2**: Uses hospital's existing table structure (`claim_rep_opip_nhso_item`, `claim_rep_orf_nhso_item`)
   - Complete field mapping: 170+ columns mapped from Excel → Database
   - Multi-database support: PostgreSQL (primary) and MySQL
   - UPSERT logic: ON CONFLICT DO UPDATE prevents duplicates on `(tran_id, file_id)` unique constraint
   - Batch imports: 100 records per batch by default
   - File types: OP, IP, ORF, IP_APPEAL, IP_APPEAL_NHSO

4. **Scheduler (`utils/scheduler.py`)**
   - APScheduler for automated downloads at scheduled times
   - Configurable via Web UI settings page
   - Optional auto-import after download
   - Background execution with process isolation

### Data Flow

```
NHSO E-Claim System
    ↓ (HTTP Client Login & Download)
eclaim_downloader_http.py
    ↓ (Excel files saved to downloads/)
Download History (download_history.json)
    ↓
utils/eclaim/parser.py (parse Excel with pandas)
    ↓
utils/eclaim/importer_v2.py (map columns)
    ↓
Database (PostgreSQL/MySQL)
    ├── eclaim_imported_files (tracking)
    ├── claim_rep_opip_nhso_item (OP/IP data)
    └── claim_rep_orf_nhso_item (ORF data)
```

### Database Schema V2

**Key Design Decisions:**
- Uses **hospital's existing table structure** as the base schema
- Adds tracking fields: `file_id`, `row_number`, HIS reconciliation columns
- Primary tables: `eclaim_imported_files`, `claim_rep_opip_nhso_item`, `claim_rep_orf_nhso_item`
- Foreign key: `file_id` references `eclaim_imported_files(id)` for tracking
- Unique constraint: `(tran_id, file_id)` prevents duplicate imports
- Timestamps: `dateadm`, `datedsc` for admission/discharge dates
- HIS reconciliation: `his_matched`, `his_vn`, `reconcile_status` for hospital system integration

**Schema Files:**
- PostgreSQL: `database/schema-postgresql-merged.sql`
- MySQL: `database/schema-mysql-merged.sql`
- Migration script: `database/migrate_to_v2.sh`

### Configuration

**Environment Variables (`.env`):**
- `ECLAIM_USERNAME`, `ECLAIM_PASSWORD` - NHSO credentials (fallback from `config/settings.json`)
- `DB_TYPE` - `postgresql` or `mysql`
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`
- `FLASK_ENV` - `development` or `production`
- `TZ` - Timezone (default: `Asia/Bangkok`)

**Settings File (`config/settings.json`):**
- Credentials, scheduler config, auto-import settings
- Managed by `SettingsManager` class
- Not in git (created from `settings.json.example`)

**Database Config (`config/database.py`):**
- Centralized DB configuration with multi-database support
- `get_db_config()` returns dict for psycopg2/pymysql
- `IMPORT_CONFIG` defines batch size, retries, timeout

### Background Processes

**Download Process:**
- Started via `utils/downloader_runner.py` subprocess
- Logs to `logs/download_YYYYMMDD_HHMMSS.log`
- Progress tracked in process state JSON
- Real-time logs streamed via SSE to web UI

**Import Process:**
- Started via `utils/import_runner.py` subprocess
- Logs to `logs/import_YYYYMMDD_HHMMSS.log`
- Progress tracked in `import_progress.json`
- Updates `eclaim_imported_files` table with status

**Scheduler:**
- APScheduler BackgroundScheduler (not blocking main thread)
- Jobs persisted in `config/settings.json`
- Initialized on app startup via `init_scheduler()`
- Can enable/disable via Web UI

### Frontend

**Technology:**
- Tailwind CSS via CDN (no build step)
- Vanilla JavaScript (`static/js/app.js`)
- Server-Sent Events (SSE) for real-time log streaming
- Fetch API for AJAX requests

**Templates (Jinja2):**
- `base.html` - Base layout with navbar
- `dashboard.html` - Statistics and file overview
- `files.html` - Paginated file list with import actions
- `download_config.html` - Single/bulk download forms
- `settings.html` - Credentials and scheduler config

## Important Implementation Notes

### When Working with Downloads

- The downloader uses **HTTP requests** (not Playwright/Selenium). If you see references to browser automation, they are legacy.
- Credentials are loaded from `config/settings.json` first, then `.env` as fallback
- Download history (`download_history.json`) prevents duplicate downloads by tracking `(month, year, file_id, repno)` tuples
- Month/year must be in Buddhist Era (Thai calendar) - add 543 to Gregorian year

### When Working with Imports

- Always use `importer_v2.py` (not legacy `importer.py`)
- Column mapping is in `OPIP_COLUMN_MAP` (49 essential fields verified against actual Excel files)
- **IMPORTANT**: Excel column names contain `\n` (newline) characters - must match exactly
  - Example: `'เรียกเก็บ\n(1)'` NOT `'เรียกเก็บ(1)'`
  - Example: `'CCUF \n(6)'` has trailing space before `\n`
  - Example: `'DMIS/ HMAIN3'` has space after `/`
- Run `fix_column_mapping.py` to verify column names match actual Excel files
- Date parsing: Thai dates handled automatically in `_map_dataframe_row()`
- Empty rows: Automatically filtered with `dropna(subset=['TRAN_ID'])`
- UPSERT: `ON CONFLICT (tran_id, file_id) DO UPDATE` prevents duplicates
- ORF files: Multi-level headers need special handling (WIP)

### When Working with Database Schema

- **DO NOT** modify the hospital's original columns in `claim_rep_opip_nhso_item` or `claim_rep_orf_nhso_item`
- **DO** add new tracking/reconciliation columns if needed (e.g., new HIS integration fields)
- Foreign key constraint: Changes to `eclaim_imported_files.id` must consider `ON DELETE` behavior
- Indexes: Add indexes on frequently queried columns (e.g., `dateadm`, `hn`, `pid`)
- Use the same schema structure for both PostgreSQL and MySQL (maintain both `.sql` files)

### When Working with Scheduler

- APScheduler uses CronTrigger (hour, minute) not full cron syntax
- Job IDs: `download_{hour:02d}_{minute:02d}` format (e.g., `download_09_00`)
- Always call `scheduler.remove_job(job_id)` before adding if job exists
- Scheduler state NOT persisted between app restarts - load from `config/settings.json` on startup

### When Working with Web UI

- Real-time logs: Use SSE endpoint `/logs/stream` consumed by EventSource
- Pagination: Files are paginated with 50 per page default
- Import status: Join `eclaim_imported_files` table via filename match
- Error handling: Return JSON with `{success: bool, message: str, error?: str}` format

## Directory Structure

```
├── app.py                     # Flask web application (main entry point)
├── eclaim_downloader_http.py  # HTTP-based downloader
├── eclaim_import.py           # CLI import tool
├── bulk_downloader.py         # Bulk download orchestrator
├── download_with_import.py    # Download wrapper with auto-import
├── requirements.txt           # Python dependencies
├── .env.example               # Environment template
├── config/
│   ├── database.py            # Database configuration
│   └── settings.json          # User settings (gitignored)
├── database/
│   ├── schema-postgresql-merged.sql  # PostgreSQL Schema V2
│   ├── schema-mysql-merged.sql       # MySQL Schema V2
│   └── migrate_to_v2.sh              # Migration script
├── utils/
│   ├── downloader_runner.py   # Background download process
│   ├── import_runner.py       # Background import process
│   ├── log_stream.py          # SSE log streaming
│   ├── scheduler.py           # APScheduler integration
│   ├── history_manager.py     # Download history CRUD
│   ├── file_manager.py        # Safe file operations
│   ├── settings_manager.py    # Settings CRUD
│   └── eclaim/
│       ├── parser.py          # Excel file parser (pandas/xlrd)
│       └── importer_v2.py     # Database importer V2
├── templates/                 # Jinja2 HTML templates
├── static/                    # CSS & JavaScript
├── downloads/                 # Downloaded Excel files
└── logs/                      # Application logs
```

## Common Development Tasks

### Adding a New Import File Type

1. Update both schema files: `database/schema-postgresql-merged.sql` and `database/schema-mysql-merged.sql`
2. Add column mapping dict in `utils/eclaim/importer_v2.py` (e.g., `NEW_TYPE_COLUMN_MAP`)
3. Implement import method: `import_new_type_batch(self, file_id, df)` in `EClaimImporterV2`
4. Update file type detection in `utils/eclaim/parser.py` if needed
5. Add migration script for existing databases

### Adding a New API Endpoint

1. Add route in `app.py`: `@app.route('/api/new-endpoint', methods=['GET', 'POST'])`
2. Return JSON: `jsonify({'success': True, 'data': ...})` or `jsonify({'success': False, 'error': ...}), 500`
3. Add frontend handler in `static/js/app.js` if needed
4. Update template if adding new UI page

### Debugging Import Issues

1. Enable debug logging: `LOG_LEVEL=DEBUG` in `.env`
2. Check import logs: `logs/import_*.log`
3. Check progress file: `import_progress.json`
4. Query database: `SELECT * FROM eclaim_imported_files WHERE filename = '...'`
5. Verify column mapping: Print `df.columns` vs `COLUMN_MAP.keys()`
6. Check data types: Ensure dates are parsed correctly (Buddhist Era → Gregorian)

### Testing Database Changes

1. Create test schema: `docker-compose exec db psql -U eclaim -d eclaim_db < database/schema-postgresql-merged.sql`
2. Test import: `docker-compose exec web python eclaim_import.py downloads/test_file.xls`
3. Verify data: `docker-compose exec db psql -U eclaim -d eclaim_db -c "SELECT * FROM claim_rep_opip_nhso_item LIMIT 5;"`
4. Check constraints: Try inserting duplicate `(tran_id, file_id)` and verify UPSERT works
5. Test MySQL: `docker-compose -f docker-compose-mysql.yml up -d` and repeat tests

## Common Issues and Solutions

### Issue: "duplicate key value violates unique constraint eclaim_imported_files_filename_key"

**Symptom:** When trying to import files, you get constraint violation errors: `duplicate key value violates unique constraint "eclaim_imported_files_filename_key"`. Import fails with 500 error.

**Cause:** Files that previously failed import are still in `eclaim_imported_files` table with `status='failed'`. When retrying import, the system tries to INSERT a new record with the same filename, violating the UNIQUE constraint on filename column.

**Solution (Fixed in current version):**
The `create_import_record()` method in `importer_v2.py` now uses UPSERT logic:
- PostgreSQL: `ON CONFLICT (filename) DO UPDATE`
- MySQL: `ON DUPLICATE KEY UPDATE`

When a duplicate filename is detected, it resets the status to 'processing' and clears error fields, allowing retry.

**Manual cleanup (if needed):**
```bash
# View failed imports
docker-compose exec -T db psql -U eclaim -d eclaim_db -c \
  "SELECT filename, status, error_message FROM eclaim_imported_files WHERE status='failed';"

# Delete failed records to retry (alternative to UPSERT)
docker-compose exec -T db psql -U eclaim -d eclaim_db -c \
  "DELETE FROM eclaim_imported_files WHERE status='failed';"
```

### Issue: "relation eclaim_claims does not exist"

**Symptom:** Database logs show attempts to INSERT into `eclaim_claims` table which doesn't exist in Schema V2.

**Cause:** Code is using legacy `importer.py` instead of `importer_v2.py`. Schema V2 uses `claim_rep_opip_nhso_item` and `claim_rep_orf_nhso_item` tables instead of `eclaim_claims`.

**Solution:**
1. Check all imports: `grep -rn "from utils.eclaim.importer import" .`
2. Replace with: `from utils.eclaim.importer_v2 import import_eclaim_file`
3. Rebuild and restart: `docker-compose build web && docker-compose up -d`

**Files to check:**
- `eclaim_downloader_http.py` (if using `import_each=True`)
- `eclaim_import.py` (should already use v2)
- Any custom scripts

### Issue: Docker Compose warning about version attribute

**Symptom:** Warning message: "the attribute `version` is obsolete, it will be ignored"

**Cause:** Docker Compose v2 no longer requires/uses the `version` key in docker-compose.yml files.

**Solution:**
Remove `version: '3.8'` line from all docker-compose files:
- `docker-compose.yml`
- `docker-compose-mysql.yml`
- `docker-compose-no-db.yml`

### Issue: Import fails with date parsing errors

**Symptom:** Errors like "time data does not match format" or dates stored incorrectly.

**Cause:** E-Claim files use Thai Buddhist Era calendar (year + 543). For example, "25681231" means 2025-12-31 in Gregorian calendar.

**Solution:** The importer_v2 handles this automatically. If you're writing custom parsers:
```python
# Thai Buddhist Era → Gregorian
thai_year = 2568
gregorian_year = thai_year - 543  # = 2025
```

### Issue: String data truncated errors

**Symptom:** Database errors about string values being too long.

**Cause:** Excel data exceeds VARCHAR column limits (e.g., VARCHAR(15) for HN).

**Solution:** The importer_v2 automatically truncates strings to column limits. Check column mapping in `OPIP_COLUMN_MAP` and adjust VARCHAR sizes in schema if needed.

### Issue: Import fails with "No columns to import" or wrong data in database

**Symptom:** Import completes but data is wrong, or import fails silently with 0 records.

**Cause:** Column names in `OPIP_COLUMN_MAP` don't match actual Excel file column names. Excel columns contain `\n` (newline) characters and extra spaces that must match exactly.

**Solution (Fixed in current version):**
- Updated OPIP_COLUMN_MAP with 49 verified column mappings
- Column names match actual Excel structure including newlines
- Use `fix_column_mapping.py` to verify mappings

**To verify correct mapping:**
```bash
# Run validation script
python fix_column_mapping.py

# Should output: ✓ Found 49/49 mapped columns
# If not, Excel file structure may have changed
```

**Common mismatches to avoid:**
- ✗ `'PID'` vs ✓ `'เลขประจำตัวประชาชน'` (should be 'PID')
- ✗ `'ชดเชยสุทธิ (บาท)\n(สปสช.)'` vs ✓ `'ชดเชยสุทธิ'`
- ✗ `'DMIS/HMAIN3'` vs ✓ `'DMIS/ HMAIN3'` (note space)
- ✗ `'เรียกเก็บ(1)'` vs ✓ `'เรียกเก็บ\n(1)'` (note \n newline)

### Issue: Health check failures on container startup

**Symptom:** Container starts but health check fails, container restarts repeatedly.

**Cause:**
- Database not ready yet (especially PostgreSQL)
- Schema not initialized
- Network connectivity issues

**Solution:**
1. Check logs: `docker-compose logs db` and `docker-compose logs web`
2. Verify database schema exists: `docker-compose exec db psql -U eclaim -d eclaim_db -c "\dt"`
3. Initialize schema if missing: `docker-compose exec -T db psql -U eclaim -d eclaim_db < database/schema-postgresql-merged.sql`
4. Check health check endpoint: `curl http://localhost:5001/dashboard`

### Issue: DNS resolution failures "Failed to resolve 'eclaim.nhso.go.th'"

**Symptom:** Download fails with error: `NameResolutionError: Failed to resolve 'eclaim.nhso.go.th' ([Errno -3] Temporary failure in name resolution)`

**Cause:** Docker's internal DNS resolver (127.0.0.11) cannot resolve external domains reliably, especially in some network configurations. This is an intermittent issue where DNS lookups sometimes succeed, sometimes fail.

**Solution (Fixed in current version):**
Added explicit DNS servers to all docker-compose files:
```yaml
dns:
  - 8.8.8.8    # Google DNS
  - 8.8.4.4    # Google DNS Secondary
  - 1.1.1.1    # Cloudflare DNS
```

**Verify the fix:**
```bash
# Check DNS config
docker-compose exec web cat /etc/resolv.conf
# Should show: ExtServers: [8.8.8.8 8.8.4.4 1.1.1.1]

# Test DNS resolution
docker-compose exec web python -c "import socket; print(socket.gethostbyname('eclaim.nhso.go.th'))"
# Should output: 122.155.147.231
```

**Alternative solutions (if still having issues):**
1. Use host network mode (not recommended for production)
2. Add to `/etc/hosts`: `122.155.147.231 eclaim.nhso.go.th`
3. Use different DNS servers (e.g., `1.0.0.1`, `208.67.222.222`)
