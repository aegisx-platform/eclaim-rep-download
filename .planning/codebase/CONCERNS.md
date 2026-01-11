# Codebase Concerns

**Analysis Date:** 2026-01-11

## Tech Debt

**Bare Exception Handlers:**
- Issue: ~~Multiple bare `except:` clauses catch all exceptions~~
- Files: `app.py`, `utils/scheduler.py`, `utils/history_manager.py`, `utils/eclaim/*.py`
- Status: ✅ FIXED (2026-01-11)
- Fix: Replaced 16 bare `except:` with specific exceptions (ValueError, TypeError, AttributeError)

**Hardcoded Flask Secret Key:**
- Issue: ~~`app.config['SECRET_KEY'] = 'eclaim-downloader-secret-key-change-in-production'`~~
- File: `app.py` (line 22)
- Status: ✅ FIXED (2026-01-11)
- Fix: Loads from `SECRET_KEY` env variable, raises error in production if not set

**No Database Connection Pooling:**
- Issue: ~~Creates new connection for each request without pooling~~
- Files: `app.py`, `config/database.py`, `config/db_pool.py`
- Status: ✅ FIXED (2026-01-11)
- Fix: Added `config/db_pool.py` with ThreadedConnectionPool, configurable via `DB_POOL_MIN`/`DB_POOL_MAX`

**Unused Playwright Dependency:**
- Issue: `playwright==1.40.0` in requirements but not used (HTTP requests used instead)
- File: `requirements.txt` (line 5)
- Why: Legacy from browser automation approach
- Impact: Bloated container image, unnecessary dependency
- Fix approach: Remove from `requirements.txt`

## Known Bugs

**Race Condition in Subscription Updates:**
- Symptoms: Web UI may not show latest download status immediately
- Trigger: Fast navigation after triggering download, before subprocess updates state
- File: `utils/downloader_runner.py`, `app.py` (status polling)
- Workaround: Refresh page or wait for status polling
- Root cause: Subprocess state file update and web UI polling not synchronized

## Security Considerations

**Credentials Stored in Plaintext:**
- Risk: File system compromise exposes NHSO credentials
- Files: `config/settings.json` (gitignored), `.env`
- Current mitigation: Files gitignored, not committed
- Recommendations: Use environment variables exclusively, consider secrets manager

**SQL Query Construction with F-Strings:**
- Risk: Future code changes could introduce SQL injection
- Files: `app.py` (lines 1287, 1292, 1494, 1506, 1518)
- Current mitigation: Currently protected by parameterized values
- Recommendations: Use parameterized queries consistently, avoid f-string SQL construction

**No Input Validation in Settings:**
- Risk: Invalid data saved to settings could cause application errors
- File: `utils/settings_manager.py`
- Current mitigation: None
- Recommendations: Add validation for credentials, schedule times, vendor IDs

## Performance Bottlenecks

**History Manager Loads All Downloads:**
- Problem: `get_statistics()` loads all downloads into memory, then filters in Python
- File: `utils/history_manager.py` (lines 71-98)
- Measurement: Slow with large datasets (10k+ downloads)
- Cause: JSON file-based storage, no query optimization
- Improvement path: Move to database storage or add pagination/caching

**Real-Time Log Streaming Inefficiency:**
- Problem: Reads entire log file and seeks for new content on every iteration
- File: `utils/log_stream.py` (lines 76-92)
- Measurement: Inefficient with large log files (100MB+)
- Cause: File-based log reading without offset tracking
- Improvement path: Use file offset tracking or event-based logging

## Fragile Areas

**Column Mapping in Importer:**
- File: `utils/eclaim/importer_v2.py` (lines 40-150)
- Why fragile: Excel column names contain `\n` (newline) characters that must match exactly
- Common failures: Import fails silently with 0 records if column names don't match
- Safe modification: Run `fix_column_mapping.py` to verify mappings before changes
- Test coverage: No tests

**Thai Date Parsing:**
- Files: `utils/eclaim/parser.py`, `utils/eclaim/importer_v2.py`
- Why fragile: Multiple date formats, Buddhist Era conversion
- Common failures: Date parsing errors, wrong year conversion
- Safe modification: Test with actual Excel files from NHSO
- Test coverage: No tests

**Scheduler State:**
- File: `utils/scheduler.py`
- Why fragile: BackgroundScheduler loses jobs on restart, relies on settings.json reload
- Common failures: Scheduled jobs not running after app restart
- Safe modification: Test startup behavior, verify jobs loaded from settings
- Test coverage: No tests

## Dependencies at Risk

**xlrd 2.0.1:**
- Risk: Only reads .xls files (not .xlsx), limited maintenance
- Impact: Can't process modern Excel files if NHSO changes format
- Migration plan: Consider openpyxl for .xlsx support if needed

## Missing Critical Features

**No Test Suite:**
- Problem: Zero test coverage for critical functions
- Current workaround: Manual testing via CLI and Docker
- Blocks: Safe refactoring, confident deployments
- Implementation complexity: Medium - need pytest setup and fixtures

**No User Authentication:**
- Problem: Web UI has no authentication
- Current workaround: Network-level access control (Docker network, firewall)
- Blocks: Multi-user deployments, audit logging
- Implementation complexity: Medium - Flask-Login or similar

## Test Coverage Gaps

**Database Import Logic:**
- What's not tested: UPSERT logic, column mapping, batch inserts
- File: `utils/eclaim/importer_v2.py`
- Risk: Import failures or data corruption undetected
- Priority: High
- Difficulty to test: Need test database and sample Excel fixtures

**Download Flow:**
- What's not tested: NHSO authentication, file download, history tracking
- File: `eclaim_downloader_http.py`
- Risk: Download failures undetected
- Priority: High
- Difficulty to test: Need mock NHSO server or test credentials

**Parser:**
- What's not tested: Filename parsing, Excel sheet detection, data extraction
- File: `utils/eclaim/parser.py`
- Risk: Parsing errors with new file formats
- Priority: Medium
- Difficulty to test: Need sample Excel files as fixtures

## Positive Findings

- Good use of environment variables for database configuration
- Atomic file writing with backup in HistoryManager
- Proper use of parameterized queries for most SQL operations
- Good separation of concerns with manager classes
- Comprehensive CLAUDE.md documentation
- Proper .gitignore (credentials not committed)
- Multi-database support (PostgreSQL/MySQL)
- Thread lock usage in LogStreamer for safety
- UPSERT logic prevents duplicate import issues

---

*Concerns audit: 2026-01-11*
*Update as issues are fixed or new ones discovered*
