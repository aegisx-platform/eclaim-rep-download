# System Architecture - v4.0.0

## Overview

E-Claim Downloader & Data Import System uses a **modular blueprint architecture** that separates concerns by domain and functionality. This architecture was introduced in v4.0.0 to improve maintainability, scalability, and team collaboration.

## Architecture Highlights

- **83.4% code reduction** in main app.py (13,657 → 2,266 lines)
- **12 domain-separated blueprints** for API routes
- **184 API routes** modularized into blueprints
- **38 core routes** remain in app.py (auth, pages, setup)
- **Clear separation of concerns** by domain

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Flask Application                     │
│                          (app.py)                            │
├─────────────────────────────────────────────────────────────┤
│  Core Routes (38 routes)                                    │
│  • Authentication (login, logout, password)                  │
│  • Page Rendering (dashboard, setup, files)                 │
│  • File Serving (download endpoints)                        │
│  • Configuration (setup wizard)                             │
└─────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     Blueprint Layer                          │
│                  (routes/*.py - 184 routes)                  │
├──────────────┬──────────────┬──────────────┬───────────────┤
│   Domain     │   Data Src   │   Utility    │   External    │
│              │              │              │               │
│ Analytics    │ REP API      │ Master Data  │ External API  │
│ Downloads    │ STM API      │ Benchmark    │ API Keys Mgmt │
│ Imports      │ SMT API      │ Jobs         │ Settings      │
│ Files        │              │ Alerts       │               │
│              │              │ System       │               │
└──────────────┴──────────────┴──────────────┴───────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Manager Layer                             │
│                  (utils/*_manager.py)                        │
├─────────────────────────────────────────────────────────────┤
│  • HistoryManager       • SettingsManager                    │
│  • FileManager          • DownloaderRunner                   │
│  • ImportRunner         • JobHistoryManager                  │
│  • AlertManager         • LicenseChecker                     │
└─────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Database Layer                             │
│            (PostgreSQL / MySQL via Pooling)                  │
├─────────────────────────────────────────────────────────────┤
│  • Connection Pooling (config/db_pool.py)                    │
│  • Multi-DB Support (PostgreSQL/MySQL)                       │
│  • Migration System (database/migrations/)                   │
│  • Row-Level Security (RLS policies)                        │
└─────────────────────────────────────────────────────────────┘
```

## Blueprint Structure

### 1. Domain Blueprints (Core Business Logic)

#### Analytics API (`routes/analytics_api.py`) - 53 routes
**Responsibility:** Business intelligence, analytics, and reporting

Routes:
- `/api/analytics/*` - General analytics endpoints
- `/api/analysis/*` - Legacy analytics (redirects)
- `/api/predictive/*` - ML-based predictions
- `/api/reconciliation/*` - Data reconciliation

Features:
- Claims analysis and trends
- Revenue forecasting
- Denial pattern detection
- Monthly/yearly aggregations
- Predictive analytics

#### Downloads API (`routes/downloads_api.py`) - 35 routes
**Responsibility:** Download orchestration and management

Routes:
- `/api/downloads/*` - Download operations
- `/api/download-history/*` - Download tracking
- `/api/v2/downloads/*` - Download manager v2

Features:
- Single/bulk downloads
- Parallel download sessions
- Progress tracking
- History management
- Retry failed downloads

#### Imports API (`routes/imports_api.py`) - 19 routes
**Responsibility:** Data import operations

Routes:
- `/api/imports/rep/*` - REP file imports
- `/api/imports/stm/*` - STM file imports
- `/api/imports/smt/*` - SMT file imports

Features:
- Batch imports
- Progress tracking
- Error handling
- File validation
- Import history

#### Files API (`routes/files_api.py`) - 15 routes
**Responsibility:** File management and operations

Routes:
- `/api/files` - File listing and operations
- `/api/files/rep/*` - REP file operations
- `/api/files/stm/*` - STM file operations
- `/api/files/smt/*` - SMT file operations

Features:
- File listing with filters
- File deletion
- Disk scanning
- Status tracking
- Re-download triggers

### 2. Data Source Blueprints

#### REP API (`routes/rep_api.py`) - 4 routes
**Responsibility:** REP data-specific operations

Routes:
- `/api/rep/file-type-stats` - File type statistics
- `/api/rep/records` - Query REP records
- `/api/rep/clear-database` - Clear REP data
- `/api/reconciliation/rep-monthly` - Monthly reconciliation

#### STM API (`routes/stm_api.py`) - 6 routes
**Responsibility:** Statement data operations

Routes:
- `/api/stm/download` - Trigger STM download
- `/api/stm/history` - STM download history
- `/api/stm/stats` - STM statistics
- `/api/stm/records` - Query STM records
- `/api/stm/clear` - Clear STM data
- `/api/stm/clear-database` - Clear STM database

#### SMT API (`routes/smt_api.py`) - 6 routes
**Responsibility:** Smart Money Transfer budget operations

Routes:
- `/api/smt/fetch` - Fetch SMT budget from NHSO
- `/api/smt/fiscal-years` - Available fiscal years
- `/api/smt/data` - Query SMT data
- `/api/smt/stats` - SMT statistics
- `/api/smt/clear` - Clear SMT data
- `/api/smt/download` - Export SMT to CSV

### 3. Utility Blueprints

#### Master Data API (`routes/master_data_api.py`) - 17 routes
**Responsibility:** Reference data management

Routes:
- `/api/master-data/*` - Master data operations
- `/api/health-offices/*` - Health office data

Features:
- NHSO error codes
- Fund types
- Service types
- Health offices lookup
- Date dimension

#### Benchmark API (`routes/benchmark_api.py`) - 7 routes
**Responsibility:** Hospital comparison and benchmarking

Routes:
- `/api/benchmark/hospitals` - Hospital list
- `/api/benchmark/timeseries` - Time-series comparison
- `/api/benchmark/my-hospital` - Own hospital analytics
- `/api/benchmark/region-average` - Regional averages
- `/api/benchmark/available-years` - Available data years

#### Jobs API (`routes/jobs_api.py`) - 3 routes
**Responsibility:** Background job tracking

Routes:
- `/api/jobs` - Job history
- `/api/jobs/stats` - Job statistics
- `/api/jobs/<job_id>` - Job details

#### Alerts API (`routes/alerts_api.py`) - 7 routes
**Responsibility:** System notifications and alerts

Routes:
- `/api/alerts` - Alert listing
- `/api/alerts/unread-count` - Unread count
- `/api/alerts/<id>/read` - Mark as read
- `/api/alerts/read-all` - Mark all read
- `/api/alerts/dismiss-all` - Dismiss all
- `/api/alerts/check-health` - Health monitoring

#### System API (`routes/system_api.py`) - 5 routes
**Responsibility:** System health and monitoring

Routes:
- `/api/system/health` - System health check
- `/api/system/seed-status` - Seed data status
- `/api/system/seed-init` - Initialize seed data
- `/api/system/seed-progress` - Seed progress
- `/api/system/sync-status` - System sync status

### 4. External Integration Blueprints

#### External API (`routes/external_api.py`) - 7 routes
**Responsibility:** HIS system integration (REST API)

Routes:
- `/api/v1/health` - API health check
- `/api/v1/claims` - Claims data export
- `/api/v1/claims/<id>` - Single claim
- `/api/v1/reconciliation/*` - HIS reconciliation

Authentication: API Key-based

#### Settings API (`routes/settings.py`) - 15 routes
**Responsibility:** System configuration

Routes:
- `/api/settings` - Settings CRUD
- `/api/settings/credentials` - Credential management
- `/api/settings/license` - License management
- `/api/schedule` - Scheduler config
- `/api/stm/schedule` - STM scheduler

#### Settings Pages (`routes/settings_pages.py`) - 8 routes
**Responsibility:** Settings UI pages

Routes:
- `/settings/*` - Settings page routes

#### API Keys Management (`routes/api_keys_management.py`) - 6 routes
**Responsibility:** API key lifecycle

Routes:
- `/api/settings/api-keys` - API keys CRUD
- API key generation, rotation, revocation

## Data Flow

### Download Flow
```
User Request → Downloads API → DownloaderRunner
                ↓
          NHSO E-Claim System
                ↓
          Downloads Directory
                ↓
          FileManager (scan)
                ↓
          Database (download_history)
```

### Import Flow
```
User Request → Imports API → ImportRunner
                ↓
          File Validation
                ↓
          Excel Parser (pandas)
                ↓
          Column Mapping
                ↓
          Database (UPSERT)
                ↓
          Import History
```

### Analytics Flow
```
User Request → Analytics API
                ↓
          Database Query
                ↓
          Aggregation/Calculation
                ↓
          Cache (if enabled)
                ↓
          JSON Response
```

## Configuration Management

### Manager Sharing Pattern
Blueprints access shared managers via `current_app.config`:

```python
# In app.py
app.config['downloader_runner'] = downloader_runner
app.config['settings_manager'] = settings_manager
app.config['file_manager'] = file_manager

# In blueprint
from flask import current_app

downloader = current_app.config['downloader_runner']
```

### Database Connection
All blueprints use pooled connections:

```python
from config.db_pool import get_pooled_connection

def my_route():
    conn = get_pooled_connection()
    try:
        # Query database
        pass
    finally:
        conn.close()  # Return to pool
```

## Security Architecture

### Authentication Layers

1. **Session-based Auth** (Web UI)
   - Flask-Login sessions
   - Password hashing (bcrypt)
   - CSRF protection

2. **API Key Auth** (External API)
   - Bearer token authentication
   - Key rotation support
   - Rate limiting per key

3. **License-based Auth** (Feature Access)
   - RSA signature verification
   - Hospital code validation
   - Feature flag enforcement

### Security Features

- **Row-Level Security (RLS)** - PostgreSQL policies
- **Audit Logging** - All critical operations
- **Rate Limiting** - Per-IP and per-user
- **Security Headers** - CSP, HSTS, etc.
- **Input Validation** - All user inputs
- **SQL Injection Prevention** - Parameterized queries
- **File Upload Security** - Type/size validation

## Deployment Architecture

### Docker Compose Stack

```yaml
services:
  web:
    image: ghcr.io/aegisx-platform/eclaim-rep-download:4.0.0
    depends_on:
      - db

  db:
    image: mysql:8.0  # or postgres:16

  nginx:  # Optional
    image: nginx:alpine
```

### Environment Configuration

- `DB_TYPE`: postgresql | mysql
- `FLASK_ENV`: development | production
- `LICENSE_MODE`: offline | online
- Feature flags via license

## Performance Considerations

### Connection Pooling
- Pool size: 5-20 connections
- Overflow: 10 connections
- Timeout: 30 seconds
- Recycle: 3600 seconds

### Caching Strategy
- In-memory caching for settings
- Database result caching (planned)
- Static file caching (nginx)

### Background Jobs
- APScheduler for scheduled tasks
- Process isolation for long-running tasks
- Job history tracking

## Migration Path

### From v3.x to v4.0
1. **No breaking changes** - All endpoints preserved
2. **Backward compatible** - Legacy routes still work
3. **Internal refactoring only** - API contracts unchanged
4. **Direct upgrade** - Pull new image and restart

### Route Migration Map
- Old: Direct `@app.route()` in app.py
- New: `@blueprint.route()` in routes/*.py
- Aliases: Legacy routes redirect to new structure

## Development Guidelines

### Adding New Endpoints

1. **Choose appropriate blueprint** based on domain
2. **Follow naming conventions**: `/api/{domain}/{resource}`
3. **Use decorators**: `@login_required`, `@require_license`
4. **Return JSON**: `jsonify({'success': bool, 'data': ...})`
5. **Handle errors**: Try/catch with proper logging

### Creating New Blueprints

```python
# routes/new_api.py
from flask import Blueprint, jsonify
import logging

new_api_bp = Blueprint('new_api', __name__)
logger = logging.getLogger('new_api')

@new_api_bp.route('/api/new/resource')
def get_resource():
    return jsonify({'success': True, 'data': []})
```

Register in `app.py`:
```python
from routes.new_api import new_api_bp
app.register_blueprint(new_api_bp)
```

## Monitoring and Observability

### Health Checks
- `/api/system/health` - Comprehensive system health
- Components: DB, disk, memory, processes, jobs
- Status levels: healthy, warning, critical

### Logging
- Structured logging (JSON format)
- Log levels: DEBUG, INFO, WARNING, ERROR
- Separate log files per blueprint
- Log rotation: 10 files, 10 MB each

### Metrics (Planned)
- Request count per endpoint
- Response time percentiles
- Error rates
- Database query performance

## Future Enhancements

### Planned Improvements
- [ ] GraphQL API layer
- [ ] WebSocket support for real-time updates
- [ ] Redis caching layer
- [ ] Message queue (Celery/RabbitMQ)
- [ ] Microservices split (analytics, downloads)
- [ ] API versioning strategy
- [ ] Auto-scaling support

### Blueprint Candidates
- Reporting API (export generation)
- Notification API (email/SMS)
- Workflow API (approval workflows)
- Integration API (third-party connectors)

## Version History

- **v4.0.0** (2026-01-19) - Modular blueprint architecture
- **v3.2.0** - License management system
- **v3.0.0** - Multi-database support
- **v2.0.0** - Production-ready release
- **v1.0.0** - Initial release

---

**Last Updated:** 2026-01-19
**Version:** 4.0.0
**Authors:** AegisX Platform Team
