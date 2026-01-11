# Coding Conventions

**Analysis Date:** 2026-01-11

## Naming Patterns

**Files:**
- snake_case for Python files: `eclaim_downloader_http.py`, `settings_manager.py`
- Versioned files: `importer_v2.py` (distinguishes from legacy `importer.py`)
- UPPERCASE.md for important docs: `README.md`, `CLAUDE.md`

**Functions:**
- snake_case for all functions: `load_settings()`, `get_eclaim_credentials()`
- Private methods start with underscore: `_load_credentials()`, `_parse_thai_date()`
- Handlers: `trigger_download()`, `start_import()`

**Variables:**
- snake_case for variables: `download_dir`, `file_manager`, `history_manager`
- Constants in UPPER_CASE: `FILE_TYPES`, `HEADER_KEYWORDS`, `OPIP_COLUMN_MAP`
- Module-level instances: `download_scheduler`, `log_streamer`

**Classes:**
- PascalCase for all classes: `EClaimDownloader`, `HistoryManager`, `EClaimFileParser`
- Suffix patterns:
  - `*Manager` for CRUD services: `HistoryManager`, `FileManager`, `SettingsManager`
  - `*Runner` for process managers: `DownloaderRunner`, `ImportRunner`
  - `*Parser` for data extraction: `EClaimFileParser`
  - `*Importer` for database insertion: `EClaimImporterV2`
  - `*Scheduler` for job scheduling: `DownloadScheduler`

**Types:**
- Type hints used in newer code: `Dict[str, str]`, `Optional[str]`, `List[Dict]`
- Example: `utils/settings_manager.py`, `smt_budget_fetcher.py`

## Code Style

**Formatting:**
- 4 spaces indentation (Python standard)
- 120 character line length (from Makefile lint target)
- Single quotes for strings: `'config/settings.json'`
- No semicolons (Python standard)

**Linting:**
- Flake8 with `--max-line-length=120`
- Excludes: `venv`, `__pycache__`
- Run: `make lint` or `docker-compose exec web python -m flake8 .`

## Import Organization

**Order:**
1. Shebang if executable: `#!/usr/bin/env python3`
2. Module docstring
3. Standard library imports
4. Third-party imports
5. Local/relative imports

**Example from `app.py`:**
```python
"""Flask Web UI for E-Claim Downloader"""

from flask import Flask, render_template, jsonify, request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import humanize
import psycopg2
from pathlib import Path

from utils import HistoryManager, FileManager, DownloaderRunner
from utils.settings_manager import SettingsManager
from config.database import get_db_config
```

**Grouping:**
- No blank lines between imports in same group
- Public APIs exported from `utils/__init__.py`

## Error Handling

**Patterns:**
- Try-except at service boundaries
- Return dict with `success` boolean and `error`/`message` keys
- Log errors before returning

**Example:**
```python
try:
    result = do_operation()
    return {'success': True, 'data': result}
except Exception as e:
    logger.error(f"Operation failed: {e}")
    return {'success': False, 'error': str(e)}
```

**Error Types:**
- Catch specific exceptions when possible
- Some bare `except:` exists (tech debt)
- Database operations: commit on success, rollback on failure

## Logging

**Framework:**
- Python `logging` module
- Per-module loggers: `logger = logging.getLogger(__name__)`

**Patterns:**
- Debug for verbose output
- Info for normal operations
- Warning for unexpected but non-fatal issues
- Error for failures

**Example:**
```python
logger = logging.getLogger(__name__)
logger.info(f"Downloading file: {filename}")
logger.error(f"Failed to download: {e}")
```

## Comments

**When to Comment:**
- Module-level docstrings on all Python files
- Class docstrings describing purpose
- Function docstrings with Args, Returns, Examples (Google style)
- Inline comments for non-obvious logic

**Module Docstring:**
```python
#!/usr/bin/env python3
"""
E-Claim XLS File Parser
Parse E-Claim Excel files (OP, IP, ORF, Appeal) and extract structured data
"""
```

**Function Docstring (Google Style):**
```python
def generate_date_range(self, start_month, start_year, end_month, end_year):
    """
    Generate list of (month, year) tuples for the date range

    Args:
        start_month (int): Starting month (1-12)
        start_year (int): Starting year in Buddhist Era

    Returns:
        list: List of (month, year) tuples

    Example:
        generate_date_range(1, 2568, 3, 2568) -> [(1,2568), (2,2568), (3,2568)]
    """
```

**TODO Comments:**
- Format: `# TODO: description`
- Some include context: `# TODO: fix race condition`

## Function Design

**Size:**
- Most functions under 50 lines
- Extract helpers for complex logic
- Some large functions in `app.py` (tech debt)

**Parameters:**
- Positional for required parameters
- Keyword arguments for optional parameters
- Type hints when clarity needed

**Return Values:**
- Explicit returns preferred
- Dict returns for complex results: `{'success': bool, 'data': ...}`
- None for void operations

## Module Design

**Exports:**
- Public API from `utils/__init__.py`:
  ```python
  from .history_manager import HistoryManager
  from .file_manager import FileManager
  from .downloader_runner import DownloaderRunner
  ```
- Direct imports for specific modules: `from utils.eclaim.importer_v2 import ...`

**Barrel Files:**
- `utils/__init__.py` exports public classes
- `config/__init__.py` exists but minimal

**Module-Level Instances:**
- Singleton-like instances created at import time
- Example in `app.py`: `history_manager = HistoryManager()`

## Flask-Specific Patterns

**Route Definitions:**
```python
@app.route('/api/endpoint', methods=['GET', 'POST'])
def endpoint_name():
    """Docstring describing endpoint"""
    pass
```

**JSON Responses:**
```python
return jsonify({'success': True, 'data': result})
return jsonify({'success': False, 'error': str(e)}), 500
```

**Template Rendering:**
```python
return render_template('page.html', context_var=value)
```

---

*Convention analysis: 2026-01-11*
*Update when patterns change*
