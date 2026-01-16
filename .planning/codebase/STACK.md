# Technology Stack

**Analysis Date:** 2026-01-11

## Languages

**Primary:**
- Python 3.12 - All application code (`Dockerfile`, `requirements.txt`)

**Secondary:**
- HTML/CSS/JavaScript - Frontend (`templates/*.html`, `static/js/app.js`)
- SQL - Database schemas (`database/schema-postgresql-merged.sql`)

## Runtime

**Environment:**
- Python 3.12 (`python:3.12-slim` Docker image)
- No browser runtime (server-side rendering with Jinja2)

**Package Manager:**
- pip
- Lockfile: None (pinned versions in `requirements.txt`)

## Frameworks

**Core:**
- Flask 3.0.0 - Web application framework (`app.py`)

**Testing:**
- None configured (no pytest in requirements, no test files)
- Flake8 lint target in Makefile (`--max-line-length=120`)

**Build/Dev:**
- Docker - Containerization (`Dockerfile`, `docker-compose.yml`)
- No build step for Python (interpreted)

## Key Dependencies

**Critical:**
- pandas 2.1.4 - Excel file parsing and data manipulation (`utils/eclaim/parser.py`)
- xlrd 2.0.1 - Reading .xls Excel files from NHSO
- requests 2.31.0 - HTTP client for NHSO e-claim downloads (`eclaim_downloader_http.py`)
- beautifulsoup4 4.12.2 - HTML parsing for NHSO pages
- APScheduler 3.10.4 - Background job scheduling (`utils/scheduler.py`)

**Infrastructure:**
- psycopg2-binary 2.9.9 - PostgreSQL driver (`config/database.py`)
- pymysql 1.1.0 - MySQL driver (alternative database)
- sqlalchemy 2.0.23 - ORM (available but not heavily used)
- python-dotenv 1.0.0 - Environment variable loading

**Utilities:**
- humanize 4.9.0 - Human-readable formatting (file sizes, dates)
- psutil 5.9.6 - Process monitoring for background tasks
- lxml 5.1.0 - XML/HTML processing

**Unused:**
- playwright 1.40.0 - Listed but not used (legacy, codebase uses HTTP requests)

## Configuration

**Environment:**
- `.env` files for secrets and database configuration
- Required: `ECLAIM_USERNAME`, `ECLAIM_PASSWORD`, `DB_*` vars
- `config/settings.json` for user-configured runtime settings (gitignored)

**Build:**
- `Dockerfile` - Application container
- `docker-compose.yml` - Multi-service orchestration
- No tsconfig/build config (Python interpreted)

## Platform Requirements

**Development:**
- Any platform with Python 3.12 and Docker
- No external dependencies beyond Python packages

**Production:**
- Docker container deployment
- Container registry: `ghcr.io/aegisx-platform/eclaim-rep-download`
- PostgreSQL 15 (or MySQL) database

---

*Stack analysis: 2026-01-11*
*Update after major dependency changes*
