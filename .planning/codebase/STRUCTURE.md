# Codebase Structure

**Analysis Date:** 2026-01-11

## Directory Layout

```
eclaim-rep-download/
├── app.py                      # Flask web application (PRIMARY ENTRY)
├── eclaim_downloader_http.py   # HTTP downloader CLI
├── eclaim_import.py            # CLI import tool
├── bulk_downloader.py          # Bulk download orchestrator
├── download_with_import.py     # Download + auto-import wrapper
├── smt_budget_fetcher.py       # SMT budget data fetcher
├── config/                     # Configuration layer
├── database/                   # Database schemas
├── utils/                      # Service layer
│   └── eclaim/                 # E-Claim specific utilities
├── templates/                  # Jinja2 HTML templates
├── static/                     # Frontend assets
├── downloads/                  # Downloaded files (gitignored)
├── logs/                       # Application logs
├── exports/                    # Exported data files
└── docs/                       # Documentation
```

## Directory Purposes

**config/**
- Purpose: Configuration and settings
- Contains: `database.py`, `settings.json.example`
- Key files:
  - `database.py` - Multi-database configuration with `get_db_config()`
  - `settings.json` - User settings (gitignored, created from example)

**database/**
- Purpose: Database schema definitions
- Contains: SQL schema files for PostgreSQL and MySQL
- Key files:
  - `schema-postgresql-merged.sql` - PostgreSQL schema
  - `schema-mysql-merged.sql` - MySQL schema
  - `IMPORT_GUIDE.md` - Import documentation

**utils/**
- Purpose: Application services and utilities
- Contains: Manager classes, runners, helpers
- Key files:
  - `history_manager.py` - Download history CRUD
  - `file_manager.py` - Safe file operations
  - `settings_manager.py` - Settings CRUD
  - `downloader_runner.py` - Download process manager
  - `import_runner.py` - Import process manager
  - `scheduler.py` - APScheduler integration
  - `log_stream.py` - SSE log streaming
  - `reconciliation.py` - HIS reconciliation logic

**utils/eclaim/**
- Purpose: E-Claim specific business logic
- Contains: Parser, importer classes
- Key files:
  - `parser.py` - XLS file parser (`EClaimFileParser`)
  - `importer_v2.py` - Database importer (`EClaimImporterV2`) - CURRENT
  - `importer.py` - Legacy importer (deprecated)
  - `importer_sheets.py` - Additional sheets importer

**templates/**
- Purpose: Web UI HTML templates
- Contains: Jinja2 templates for all pages
- Key files:
  - `base.html` - Base layout with navbar
  - `dashboard.html` - Main dashboard
  - `files.html` - File list with pagination
  - `download_config.html` - Download configuration
  - `settings.html` - Settings/credentials page
  - `analytics.html` - Analytics/reports
  - `reconciliation.html` - HIS reconciliation
  - `smt_budget.html` - SMT budget features

**static/**
- Purpose: Frontend assets
- Contains: CSS, JavaScript
- Key files:
  - `js/app.js` - Frontend JavaScript (AJAX, SSE, polling)
  - `css/custom.css` - Custom styles (Tailwind via CDN)

**docs/**
- Purpose: User and developer documentation
- Contains: Markdown documentation files
- Key files:
  - `INSTALLATION.md`, `CONFIGURATION.md`, `USAGE.md`
  - `DEVELOPMENT.md`, `TROUBLESHOOTING.md`
  - `DATABASE.md`, `FEATURES.md`

## Key File Locations

**Entry Points:**
- `app.py` - Flask web application (port 5001)
- `eclaim_downloader_http.py` - HTTP downloader executable
- `eclaim_import.py` - CLI import tool
- `bulk_downloader.py` - Multi-month download orchestrator

**Configuration:**
- `config/database.py` - Database connection config
- `config/settings.json` - Runtime settings (gitignored)
- `.env` - Environment variables (gitignored)
- `.env.example` - Environment template

**Core Logic:**
- `utils/eclaim/importer_v2.py` - Database importer (49-column mapping)
- `utils/eclaim/parser.py` - Excel file parser
- `eclaim_downloader_http.py` - NHSO authentication and download

**Testing:**
- No test files present
- `Makefile` has lint target (`flake8 --max-line-length=120`)

**Documentation:**
- `README.md` - User-facing documentation
- `CLAUDE.md` - Claude Code instructions
- `DOCKER.md` - Docker deployment guide

## Naming Conventions

**Files:**
- snake_case for all Python files: `eclaim_downloader_http.py`
- UPPERCASE.md for important docs: `README.md`, `CLAUDE.md`
- Versioned files: `importer_v2.py` (distinguishes from legacy)

**Directories:**
- All lowercase: `config/`, `utils/`, `templates/`
- Plural for collections: `templates/`, `downloads/`, `logs/`

**Classes:**
- PascalCase: `EClaimDownloader`, `HistoryManager`, `EClaimFileParser`
- Suffix pattern: `*Manager`, `*Runner`, `*Parser`, `*Importer`

**Special Patterns:**
- `*_runner.py` - Background process managers
- `*_manager.py` - CRUD service classes
- `schema-{db}-*.sql` - Database schemas

## Where to Add New Code

**New Feature:**
- Primary code: `utils/` directory
- Web routes: Add to `app.py`
- Templates: `templates/` directory
- Config if needed: `config/`

**New Manager/Service:**
- Implementation: `utils/{name}_manager.py`
- Import in: `utils/__init__.py` for public API
- Use in: `app.py` or CLI tools

**New E-Claim Logic:**
- Implementation: `utils/eclaim/{name}.py`
- Parser changes: `utils/eclaim/parser.py`
- Import changes: `utils/eclaim/importer_v2.py`

**New CLI Tool:**
- Implementation: Root directory `{name}.py`
- Pattern: Follow `eclaim_import.py` structure
- Add to: Dockerfile if needed for container

**New Web Page:**
- Template: `templates/{name}.html` (extends base.html)
- Route: Add to `app.py`
- JavaScript: Update `static/js/app.js` if needed

**Utilities:**
- Shared helpers: `utils/` directory
- E-Claim specific: `utils/eclaim/`

## Special Directories

**downloads/**
- Purpose: Downloaded Excel files from NHSO
- Source: Created by downloader
- Committed: No (gitignored)

**logs/**
- Purpose: Application log files
- Source: Generated by application
- Committed: No (gitignored)

**exports/**
- Purpose: Exported data (CSV, etc.)
- Source: Generated by export features
- Committed: No (gitignored)

**.planning/**
- Purpose: GSD planning documents
- Source: Created by this workflow
- Committed: Yes

---

*Structure analysis: 2026-01-11*
*Update when directory structure changes*
