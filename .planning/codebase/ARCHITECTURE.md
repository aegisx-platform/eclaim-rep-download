# Architecture

**Analysis Date:** 2026-01-11

## Pattern Overview

**Overall:** Layered Monolith with Flask Web UI + CLI Tools

**Key Characteristics:**
- Single codebase with web UI and standalone CLI tools
- Background process isolation (subprocess spawning)
- Event streaming via Server-Sent Events (SSE)
- Multi-database support (PostgreSQL/MySQL)
- File-based state tracking (JSON files)

## Layers

**Presentation Layer:**
- Purpose: HTTP endpoints and web UI rendering
- Contains: Flask routes, Jinja2 templates, JavaScript
- Location: `app.py`, `templates/`, `static/`
- Depends on: Service layer (managers, runners)
- Used by: Browser clients

**Service/Manager Layer:**
- Purpose: Business logic orchestration
- Contains: Manager classes for different domains
- Location: `utils/*.py`
- Depends on: Data layer, utility layer
- Used by: Presentation layer, CLI tools

**Business Logic Layer:**
- Purpose: Core domain logic
- Contains: Downloader, importer, parser classes
- Location: `eclaim_downloader_http.py`, `utils/eclaim/`
- Depends on: Utility layer, external services
- Used by: Service layer, CLI entry points

**Data/Configuration Layer:**
- Purpose: Persistence and configuration
- Contains: Database config, settings management
- Location: `config/`, JSON state files
- Depends on: File system, database drivers
- Used by: All layers

## Data Flow

**Download Flow:**
1. User triggers download via Web UI or scheduler
2. `DownloaderRunner` spawns subprocess (`eclaim_downloader_http.py`)
3. `EClaimDownloader` authenticates with NHSO
4. Downloads Excel files to `downloads/` directory
5. Updates `download_history.json` for deduplication
6. Logs streamed via SSE to web UI

**Import Flow:**
1. User triggers import via Web UI
2. `ImportRunner` spawns subprocess (`eclaim_import.py`)
3. `EClaimFileParser` extracts metadata and data (pandas)
4. `EClaimImporterV2` maps columns and inserts to database
5. UPSERT logic handles duplicates (`ON CONFLICT DO UPDATE`)
6. Updates `eclaim_imported_files` table with status
7. Progress tracked in `import_progress.json`

**Scheduler Flow:**
1. App startup initializes `DownloadScheduler` (APScheduler)
2. Loads schedule from `config/settings.json`
3. CronTrigger jobs run at specified times
4. Spawns download subprocess
5. Optional auto-import after download completes

**State Management:**
- File-based: JSON files for history, progress, settings
- Database: Imported data, tracking records
- No in-memory persistence across requests

## Key Abstractions

**Manager (Service Pattern):**
- Purpose: Encapsulate domain-specific operations
- Examples: `HistoryManager`, `FileManager`, `SettingsManager`
- Pattern: Singleton-like (module-level instances in `app.py`)
- Location: `utils/history_manager.py`, `utils/file_manager.py`, `utils/settings_manager.py`

**Runner (Process Management):**
- Purpose: Manage background subprocess lifecycle
- Examples: `DownloaderRunner`, `ImportRunner`
- Pattern: Spawn subprocess, track PID, poll status
- Location: `utils/downloader_runner.py`, `utils/import_runner.py`

**Parser/Importer (Data Pipeline):**
- Purpose: Transform external data for database storage
- Examples: `EClaimFileParser`, `EClaimImporterV2`
- Pattern: Extract metadata, map columns, batch insert
- Location: `utils/eclaim/parser.py`, `utils/eclaim/importer_v2.py`

**Scheduler (Job Management):**
- Purpose: Time-based task execution
- Examples: `DownloadScheduler`
- Pattern: APScheduler BackgroundScheduler with CronTrigger
- Location: `utils/scheduler.py`

## Entry Points

**Web Application:**
- Location: `app.py`
- Triggers: HTTP requests to port 5001
- Responsibilities: Serve UI, REST API endpoints, SSE streaming

**CLI Downloader:**
- Location: `eclaim_downloader_http.py`
- Triggers: Direct execution or subprocess spawn
- Responsibilities: Authenticate with NHSO, download files

**CLI Importer:**
- Location: `eclaim_import.py`
- Triggers: Direct execution or subprocess spawn
- Responsibilities: Parse Excel, insert to database

**Bulk Downloader:**
- Location: `bulk_downloader.py`
- Triggers: Direct execution
- Responsibilities: Orchestrate multi-month downloads

## Error Handling

**Strategy:** Try-except at boundaries, log errors, return status

**Patterns:**
- Managers catch exceptions and return success/failure dicts
- Runners track subprocess exit codes
- Database operations wrapped in try-except with rollback
- Web routes return JSON with `success` boolean and `error` message

**Logging:**
- Python `logging` module throughout
- Application logs to `logs/` directory
- Real-time streaming via `utils/log_stream.py`

## Cross-Cutting Concerns

**Logging:**
- Python logging with file handlers
- SSE streaming for real-time UI (`/logs/stream`)
- Thread-safe LogStreamer class

**Configuration:**
- Hierarchy: `settings.json` > `.env` > defaults
- `SettingsManager` provides unified access
- Environment variables for secrets

**Database Abstraction:**
- `config/database.py` provides `get_db_config()`
- Conditional imports for PostgreSQL/MySQL
- Same SQL with minor dialect differences

**Process Isolation:**
- Background tasks run as subprocesses
- PID tracking in temp files
- Prevents blocking main Flask thread

---

*Architecture analysis: 2026-01-11*
*Update when major patterns change*
