# Download Manager Design Document

> **Version:** 1.0
> **Date:** 2026-01-18
> **Status:** Draft
> **Author:** Claude Code

---

## Executive Summary

This document describes the design of a standardized Download Management system for the e-Claim application. The new system addresses critical issues with progress tracking, provides accurate real-time status updates, and creates a reusable core that works with multiple download sources (REP, STM, SMT).

### Key Improvements

1. **Accurate Progress Tracking** - Shows processed files (downloaded + skipped), not just new downloads
2. **Pre-fetch File Discovery** - Knows total file count and already-downloaded status before starting
3. **Database-backed Sessions** - Persistent session tracking survives server restarts
4. **Cancel & Resume Support** - Graceful cancellation with ability to resume
5. **Event-driven Architecture** - Clean separation for future UI changes

---

## Current Problems Analysis

### Problem 1: Progress Counter Shows Wrong Numbers

**Symptom:** UI shows "0/394 files" while logs show "387/394" being processed.

**Root Cause Analysis:**

```python
# Current parallel_downloader.py progress update (line 614-618)
self._update_progress(
    completed=completed,   # Only counts NEW downloads (2)
    failed=failed,
    skipped=skipped,       # Skipped count is 392, but not reflected in UI
)
```

The progress JSON correctly tracks:
```json
{
  "total": 394,
  "completed": 2,      // New downloads
  "skipped": 392,      // Already downloaded - NOT shown in UI progress
  "failed": 0
}
```

However, the frontend displays:
```javascript
// static/js/app.js line 1017-1018
const completed = progress.completed || 0;  // Shows 2
const total = progress.total || 0;          // Shows 394
// Result: "2/394 files" - ignores 392 skipped!
```

**Solution:** UI should show `processed = completed + skipped` as the numerator.

### Problem 2: No Pre-fetch Phase

**Current Flow:**
```
1. Login to NHSO
2. For each file in page:
   a. Check if exists in history -> Skip or Download
   b. Update progress
3. Done
```

**Problem:** Total file count is discovered during download, not before. Initial progress shows "0/0".

**Desired Flow:**
```
1. Login to NHSO
2. Fetch file list (394 files)
3. Compare with database (387 already downloaded)
4. Calculate: to_download=7, already_downloaded=387
5. Initialize progress with accurate totals
6. Download only 7 files
7. Report accurate progress throughout
```

### Problem 3: File-based Progress (Not Durable)

Current system uses JSON files for progress:
- `parallel_download_progress.json`
- `bulk_download_progress.json`
- `download_iteration_progress.json`

**Problems:**
- Lost on container restart
- Race conditions with multiple readers/writers
- No history/audit trail
- Can't resume after crash

### Problem 4: Duplicate Code Across Downloaders

Three separate implementations with similar logic:
- `eclaim_downloader_http.py` (single download)
- `stm_downloader_http.py` (STM download)
- `utils/parallel_downloader.py` (parallel download)

Each implements its own:
- Progress tracking
- History checking
- Error handling
- Retry logic

---

## Architecture Design

### High-Level Architecture

```
+------------------+     +-------------------+     +------------------+
|   Frontend UI    |<--->|   REST API        |<--->|  Download        |
|   (JavaScript)   |     |   (Flask Routes)  |     |  Manager Core    |
+------------------+     +-------------------+     +------------------+
                                                          |
                                                          v
                              +------------------------------------------+
                              |           Download Manager               |
                              |------------------------------------------|
                              |  +-------------+  +------------------+   |
                              |  | Session     |  | Progress         |   |
                              |  | Manager     |  | Tracker          |   |
                              |  +-------------+  +------------------+   |
                              |         |                |               |
                              |         v                v               |
                              |  +-------------+  +------------------+   |
                              |  | File        |  | Event            |   |
                              |  | Discoverer  |  | Emitter          |   |
                              |  +-------------+  +------------------+   |
                              |         |                               |
                              |         v                               |
                              |  +------------------------------------+ |
                              |  |     Source Adapters                | |
                              |  | +-------+ +-------+ +-------+      | |
                              |  | | REP   | | STM   | | SMT   |      | |
                              |  | +-------+ +-------+ +-------+      | |
                              |  +------------------------------------+ |
                              +------------------------------------------+
                                                   |
                                                   v
                              +------------------------------------------+
                              |              Database                    |
                              |  +------------------+  +---------------+ |
                              |  | download_sessions|  | download_files| |
                              |  +------------------+  +---------------+ |
                              +------------------------------------------+
```

### Component Responsibilities

#### 1. Download Manager Core (`utils/download_manager.py`)

**Responsibilities:**
- Orchestrates the download workflow
- Manages session lifecycle
- Coordinates between components
- Provides unified interface for all download types

**Key Methods:**
```python
class DownloadManager:
    def __init__(self, source_type: str, credentials: List[Dict], config: Dict)

    # Session Management
    def create_session(self, params: Dict) -> str          # Returns session_id
    def get_session(self, session_id: str) -> DownloadSession
    def cancel_session(self, session_id: str) -> bool
    def resume_session(self, session_id: str) -> bool

    # Execution
    def start(self) -> str                                  # Returns session_id
    def run_sync(self) -> DownloadResult                    # Blocking execution

    # Status
    def get_progress(self, session_id: str) -> ProgressInfo
    def get_history(self, limit: int = 50) -> List[SessionSummary]
```

#### 2. Session Manager

**Responsibilities:**
- Creates and manages download sessions
- Persists session state to database
- Handles session lifecycle (pending, running, completed, failed, cancelled)

**State Machine:**
```
              +-----------+
              |  PENDING  |
              +-----+-----+
                    |
                    v
              +-----------+
    +-------->| RUNNING   |<---------+
    |         +-----+-----+          |
    |               |                |
    |    +----------+----------+     |
    |    |          |          |     |
    |    v          v          v     |
+---+----+   +----------+  +--------+|
|CANCELLED|  |COMPLETED |  | FAILED |+
+---------+  +----------+  +--------+
    |                          |
    v                          |
+---------+                    |
|RESUMABLE|<-------------------+
+---------+
```

#### 3. Progress Tracker

**Responsibilities:**
- Tracks real-time download progress
- Maintains accurate counts (total, processed, downloaded, skipped, failed)
- Persists progress to database for durability
- Emits progress events for UI updates

**Progress Model:**
```python
@dataclass
class ProgressInfo:
    session_id: str
    status: SessionStatus

    # Discovery Phase
    total_discovered: int        # Files found on source (e.g., 394)
    discovery_completed: bool

    # Comparison Phase
    already_downloaded: int      # Files in history (e.g., 387)
    to_download: int             # Files needing download (e.g., 7)

    # Execution Phase
    processed: int               # Files checked (downloaded + skipped + failed)
    downloaded: int              # New files downloaded
    skipped: int                 # Files skipped (already exist)
    failed: int                  # Failed downloads

    # Current State
    current_file: Optional[str]
    current_worker: Optional[str]

    # Timing
    started_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]
    eta_seconds: Optional[int]

    # Control
    cancellable: bool
    resumable: bool

    # Computed Properties
    @property
    def progress_percent(self) -> float:
        if self.total_discovered == 0:
            return 0
        return (self.processed / self.total_discovered) * 100

    @property
    def is_complete(self) -> bool:
        return self.processed == self.total_discovered
```

#### 4. File Discoverer

**Responsibilities:**
- Fetches file list from source before downloading
- Compares against existing downloads in database
- Categorizes files into: to_download, already_downloaded, retry_failed

**Interface:**
```python
class FileDiscoverer:
    def discover(self, source: SourceAdapter) -> FileDiscoveryResult

@dataclass
class FileDiscoveryResult:
    discovered_at: datetime
    total_files: int
    files: List[FileInfo]

    to_download: List[FileInfo]
    already_downloaded: List[FileInfo]
    retry_failed: List[FileInfo]  # Previously failed, can retry

@dataclass
class FileInfo:
    filename: str
    url: str
    file_type: str       # OP, IP, ORF, etc.
    size_hint: Optional[int]
    metadata: Dict
```

#### 5. Event Emitter

**Responsibilities:**
- Emits events for all download activities
- Enables UI updates via SSE
- Supports multiple listeners (logging, metrics, etc.)

**Events:**
```python
class DownloadEvents:
    # Discovery Phase
    SESSION_CREATED = "session.created"
    DISCOVERY_STARTED = "discovery.started"
    DISCOVERY_COMPLETED = "discovery.completed"

    # Execution Phase
    DOWNLOAD_STARTED = "download.started"
    FILE_CHECK_START = "file.check.start"
    FILE_CHECK_COMPLETE = "file.check.complete"
    FILE_DOWNLOAD_START = "file.download.start"
    FILE_DOWNLOAD_PROGRESS = "file.download.progress"
    FILE_DOWNLOAD_COMPLETE = "file.download.complete"
    FILE_SKIP = "file.skip"
    FILE_FAIL = "file.fail"

    # Session Phase
    DOWNLOAD_COMPLETE = "download.complete"
    DOWNLOAD_CANCELLED = "download.cancelled"
    DOWNLOAD_FAILED = "download.failed"

    # Progress
    PROGRESS_UPDATE = "progress.update"
```

#### 6. Source Adapters

**Responsibilities:**
- Abstract different download sources (REP, STM, SMT)
- Handle source-specific authentication
- Implement file list fetching and file downloading

**Interface:**
```python
class SourceAdapter(ABC):
    @abstractmethod
    def get_source_type(self) -> str:
        """Return source type identifier (rep, stm, smt)"""
        pass

    @abstractmethod
    def authenticate(self, credentials: Dict) -> AuthResult:
        """Authenticate with source"""
        pass

    @abstractmethod
    def fetch_file_list(self, params: Dict) -> List[FileInfo]:
        """Fetch list of available files from source"""
        pass

    @abstractmethod
    def download_file(self, file_info: FileInfo, dest_path: Path) -> DownloadResult:
        """Download a single file"""
        pass

    @abstractmethod
    def validate_file(self, file_path: Path, file_info: FileInfo) -> bool:
        """Validate downloaded file"""
        pass
```

**Implementations:**
```python
class REPSourceAdapter(SourceAdapter):
    """Adapter for REP (e-Claim) downloads via web scraping"""
    def get_source_type(self) -> str:
        return "rep"

    def fetch_file_list(self, params: Dict) -> List[FileInfo]:
        # Login to NHSO e-claim portal
        # Scrape file list from HTML table
        # Return FileInfo objects

class STMSourceAdapter(SourceAdapter):
    """Adapter for Statement downloads via web scraping"""
    def get_source_type(self) -> str:
        return "stm"

    def fetch_file_list(self, params: Dict) -> List[FileInfo]:
        # Login to STM portal
        # Parse file list from HTML
        # Return FileInfo objects

class SMTSourceAdapter(SourceAdapter):
    """Adapter for Smart Money Transfer via API"""
    def get_source_type(self) -> str:
        return "smt"

    def fetch_file_list(self, params: Dict) -> List[FileInfo]:
        # Call NHSO SMT API
        # Parse JSON response
        # Return FileInfo objects (virtual files for DB import)
```

### Adding New Sources (Extensibility)

The adapter pattern makes it easy to add new download sources **without modifying core code**.

#### Example: Adding a New Source (Claims Processing System - CPS)

**Step 1: Create New Adapter**
```python
# utils/download_manager/adapters/cps.py

from .base import SourceAdapter, FileInfo, AuthResult, DownloadResult
from typing import Dict, List
import requests

class CPSSourceAdapter(SourceAdapter):
    """
    Adapter for Claims Processing System (CPS) API
    Source Type: API-based download
    """

    def get_source_type(self) -> str:
        return "cps"

    def authenticate(self, credentials: Dict) -> AuthResult:
        """Authenticate with CPS API"""
        response = requests.post(
            "https://cps.nhso.go.th/api/v1/auth",
            json={
                "api_key": credentials.get("api_key"),
                "secret": credentials.get("secret")
            }
        )

        if response.status_code == 200:
            self._token = response.json()["access_token"]
            return AuthResult(success=True, token=self._token)
        else:
            return AuthResult(success=False, error=response.text)

    def fetch_file_list(self, params: Dict) -> List[FileInfo]:
        """Fetch available files from CPS API"""
        fiscal_year = params.get("fiscal_year")
        hospital_code = params.get("hospital_code")

        response = requests.get(
            f"https://cps.nhso.go.th/api/v1/files",
            headers={"Authorization": f"Bearer {self._token}"},
            params={
                "fiscal_year": fiscal_year,
                "hospital": hospital_code,
                "file_type": "claims"
            }
        )

        files = []
        for item in response.json()["data"]:
            files.append(FileInfo(
                filename=item["filename"],
                url=item["download_url"],
                file_type=item["type"],
                size_hint=item["size_bytes"],
                metadata={
                    "file_id": item["id"],
                    "created_at": item["created_at"],
                    "claim_count": item["claim_count"]
                }
            ))

        return files

    def download_file(self, file_info: FileInfo, dest_path: Path) -> DownloadResult:
        """Download file from CPS API"""
        response = requests.get(
            file_info.url,
            headers={"Authorization": f"Bearer {self._token}"},
            stream=True
        )

        if response.status_code == 200:
            with open(dest_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            return DownloadResult(
                success=True,
                file_path=dest_path,
                file_size=dest_path.stat().st_size
            )
        else:
            return DownloadResult(
                success=False,
                error=f"HTTP {response.status_code}: {response.text}"
            )

    def validate_file(self, file_path: Path, file_info: FileInfo) -> bool:
        """Validate downloaded file"""
        # Check file size matches
        actual_size = file_path.stat().st_size
        expected_size = file_info.size_hint

        if expected_size and abs(actual_size - expected_size) > 1024:
            return False

        # Verify file is valid Excel/CSV
        try:
            import pandas as pd
            df = pd.read_excel(file_path) if file_path.suffix == '.xls' else pd.read_csv(file_path)
            return len(df) > 0
        except Exception:
            return False
```

**Step 2: Register Adapter**
```python
# utils/download_manager/adapters/__init__.py

from .base import SourceAdapter
from .rep import REPSourceAdapter
from .stm import STMSourceAdapter
from .smt import SMTSourceAdapter
from .cps import CPSSourceAdapter  # ← New adapter

# Adapter registry (auto-discovery)
ADAPTER_REGISTRY = {
    'rep': REPSourceAdapter,
    'stm': STMSourceAdapter,
    'smt': SMTSourceAdapter,
    'cps': CPSSourceAdapter,  # ← Register here
}

def get_adapter(source_type: str) -> SourceAdapter:
    """Factory function to get adapter by source type"""
    adapter_class = ADAPTER_REGISTRY.get(source_type)
    if not adapter_class:
        raise ValueError(f"Unknown source type: {source_type}")
    return adapter_class()
```

**Step 3: Add Database Config (Optional)**
```python
# config/download_sources.py

DOWNLOAD_SOURCES = {
    'rep': {
        'name': 'REP Files (e-Claim)',
        'type': 'web',
        'max_workers': 3,
        'requires_credentials': True,
        'supports_bulk': True,
        'icon': 'file-medical'
    },
    'stm': {
        'name': 'STM Files (Statement)',
        'type': 'web',
        'max_workers': 2,
        'requires_credentials': True,
        'supports_bulk': True,
        'icon': 'file-invoice'
    },
    'smt': {
        'name': 'SMT Data (API)',
        'type': 'api',
        'max_workers': 1,
        'requires_credentials': True,
        'supports_bulk': False,
        'icon': 'database'
    },
    'cps': {  # ← New source config
        'name': 'CPS Claims (API)',
        'type': 'api',
        'max_workers': 2,
        'requires_credentials': True,
        'supports_bulk': True,
        'icon': 'chart-line'
    }
}
```

**Step 4: Update Frontend (Automatic Discovery)**
```javascript
// Frontend automatically discovers new sources from API

fetch('/api/v2/downloads/sources')
    .then(r => r.json())
    .then(data => {
        // Render download cards for all available sources
        data.sources.forEach(source => {
            renderDownloadCard({
                type: source.type,        // 'cps'
                name: source.name,        // 'CPS Claims (API)'
                icon: source.icon,        // 'chart-line'
                maxWorkers: source.max_workers
            });
        });
    });
```

**Step 5: Use New Source (No Core Changes Needed!)**
```bash
# API call to start CPS download
POST /api/v2/downloads/sessions
{
    "source_type": "cps",
    "fiscal_year": 2569,
    "hospital_code": "10670",
    "credentials": {
        "api_key": "...",
        "secret": "..."
    }
}

# Download Manager automatically:
# 1. Loads CPSSourceAdapter from registry
# 2. Creates isolated session
# 3. Runs download with progress tracking
# 4. All existing features work (cancel, resume, events, etc.)
```

#### Template for New Adapter

```python
# utils/download_manager/adapters/my_new_source.py

from .base import SourceAdapter, FileInfo, AuthResult, DownloadResult
from typing import Dict, List
from pathlib import Path

class MyNewSourceAdapter(SourceAdapter):
    """
    Adapter for [SOURCE NAME]

    Source Type: [web/api]
    Authentication: [credentials required/optional]
    Bulk Download: [yes/no]
    """

    def get_source_type(self) -> str:
        """Return unique source identifier"""
        return "my_source"

    def authenticate(self, credentials: Dict) -> AuthResult:
        """
        Authenticate with source

        Args:
            credentials: Dict with auth info (username/password or API key)

        Returns:
            AuthResult with success status and token/error
        """
        # TODO: Implement authentication logic
        pass

    def fetch_file_list(self, params: Dict) -> List[FileInfo]:
        """
        Fetch list of available files

        Args:
            params: Download parameters (fiscal_year, month, etc.)

        Returns:
            List of FileInfo objects
        """
        # TODO: Implement file discovery logic
        # For web: scrape HTML table/links
        # For API: call endpoint and parse JSON
        pass

    def download_file(self, file_info: FileInfo, dest_path: Path) -> DownloadResult:
        """
        Download a single file

        Args:
            file_info: File metadata from fetch_file_list()
            dest_path: Where to save the file

        Returns:
            DownloadResult with success status
        """
        # TODO: Implement download logic
        # Use requests for HTTP download
        # Handle streaming for large files
        pass

    def validate_file(self, file_path: Path, file_info: FileInfo) -> bool:
        """
        Validate downloaded file

        Args:
            file_path: Path to downloaded file
            file_info: Original file metadata

        Returns:
            True if valid, False otherwise
        """
        # TODO: Implement validation logic
        # Check file size, format, integrity
        pass
```

### Benefits of Adapter Pattern

1. **Zero Core Changes** - Add new sources without modifying DownloadManager
2. **Type Safety** - Abstract base enforces interface contract
3. **Auto-Discovery** - Registry pattern finds adapters automatically
4. **Consistent UX** - All sources get same progress tracking, cancel/resume, etc.
5. **Easy Testing** - Mock adapters for unit tests
6. **Future-Proof** - New NHSO systems or APIs? Just add adapter!

---

## Database Schema

### New Tables

```sql
-- =============================================================================
-- PostgreSQL Version
-- =============================================================================

-- Download Sessions: Track each download run
CREATE TABLE IF NOT EXISTS download_sessions (
    id              VARCHAR(36) PRIMARY KEY,      -- UUID
    source_type     VARCHAR(20) NOT NULL,         -- rep, stm, smt
    status          VARCHAR(20) NOT NULL,         -- pending, discovering, downloading,
                                                  -- completed, failed, cancelled

    -- Parameters
    fiscal_year     INTEGER,
    service_month   INTEGER,
    scheme          VARCHAR(20),
    params          JSONB,                        -- Additional source-specific params

    -- Discovery Results
    total_discovered    INTEGER DEFAULT 0,
    already_downloaded  INTEGER DEFAULT 0,
    to_download         INTEGER DEFAULT 0,
    retry_failed        INTEGER DEFAULT 0,

    -- Execution Results
    processed       INTEGER DEFAULT 0,
    downloaded      INTEGER DEFAULT 0,
    skipped         INTEGER DEFAULT 0,
    failed          INTEGER DEFAULT 0,

    -- Worker Info
    max_workers     INTEGER DEFAULT 1,
    worker_info     JSONB,                        -- Worker status array

    -- Timing
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at      TIMESTAMP,
    completed_at    TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Control
    cancellable     BOOLEAN DEFAULT TRUE,
    resumable       BOOLEAN DEFAULT TRUE,
    cancelled_at    TIMESTAMP,
    resume_count    INTEGER DEFAULT 0,

    -- Error Info
    error_message   TEXT,
    error_details   JSONB,

    -- Metadata
    triggered_by    VARCHAR(50),                  -- manual, scheduler, api
    notes           TEXT
);

-- Indexes for download_sessions
CREATE INDEX IF NOT EXISTS idx_ds_source_type ON download_sessions(source_type);
CREATE INDEX IF NOT EXISTS idx_ds_status ON download_sessions(status);
CREATE INDEX IF NOT EXISTS idx_ds_created ON download_sessions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ds_fiscal_year ON download_sessions(fiscal_year);

-- Download Files: Track individual files in a session
CREATE TABLE IF NOT EXISTS download_session_files (
    id              BIGSERIAL PRIMARY KEY,
    session_id      VARCHAR(36) NOT NULL REFERENCES download_sessions(id) ON DELETE CASCADE,

    -- File Info
    filename        VARCHAR(255) NOT NULL,
    file_url        TEXT,
    file_type       VARCHAR(20),                  -- OP, IP, ORF, etc.

    -- Status
    status          VARCHAR(20) NOT NULL,         -- pending, downloading, completed,
                                                  -- skipped, failed
    skip_reason     VARCHAR(50),                  -- already_exists, duplicate, etc.

    -- Result
    file_size       BIGINT,
    file_path       VARCHAR(500),
    file_hash       VARCHAR(64),

    -- Timing
    queued_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at      TIMESTAMP,
    completed_at    TIMESTAMP,

    -- Worker
    worker_id       INTEGER,
    worker_name     VARCHAR(50),

    -- Retry
    retry_count     INTEGER DEFAULT 0,
    error_message   TEXT,

    -- Metadata
    source_metadata JSONB                         -- Original file info from source
);

-- Indexes for download_session_files
CREATE INDEX IF NOT EXISTS idx_dsf_session ON download_session_files(session_id);
CREATE INDEX IF NOT EXISTS idx_dsf_status ON download_session_files(status);
CREATE INDEX IF NOT EXISTS idx_dsf_filename ON download_session_files(filename);
CREATE UNIQUE INDEX IF NOT EXISTS idx_dsf_session_file ON download_session_files(session_id, filename);

-- Session Events: Audit trail for debugging
CREATE TABLE IF NOT EXISTS download_session_events (
    id              BIGSERIAL PRIMARY KEY,
    session_id      VARCHAR(36) NOT NULL REFERENCES download_sessions(id) ON DELETE CASCADE,

    event_type      VARCHAR(50) NOT NULL,
    event_data      JSONB,

    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dse_session ON download_session_events(session_id);
CREATE INDEX IF NOT EXISTS idx_dse_type ON download_session_events(event_type);
```

### MySQL Version

```sql
-- =============================================================================
-- MySQL Version
-- =============================================================================

CREATE TABLE IF NOT EXISTS download_sessions (
    id              VARCHAR(36) PRIMARY KEY,
    source_type     VARCHAR(20) NOT NULL,
    status          VARCHAR(20) NOT NULL,

    fiscal_year     INT,
    service_month   INT,
    scheme          VARCHAR(20),
    params          JSON,

    total_discovered    INT DEFAULT 0,
    already_downloaded  INT DEFAULT 0,
    to_download         INT DEFAULT 0,
    retry_failed        INT DEFAULT 0,

    processed       INT DEFAULT 0,
    downloaded      INT DEFAULT 0,
    skipped         INT DEFAULT 0,
    failed          INT DEFAULT 0,

    max_workers     INT DEFAULT 1,
    worker_info     JSON,

    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    started_at      DATETIME,
    completed_at    DATETIME,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    cancellable     BOOLEAN DEFAULT TRUE,
    resumable       BOOLEAN DEFAULT TRUE,
    cancelled_at    DATETIME,
    resume_count    INT DEFAULT 0,

    error_message   TEXT,
    error_details   JSON,

    triggered_by    VARCHAR(50),
    notes           TEXT,

    INDEX idx_ds_source_type (source_type),
    INDEX idx_ds_status (status),
    INDEX idx_ds_created (created_at DESC),
    INDEX idx_ds_fiscal_year (fiscal_year)
);

CREATE TABLE IF NOT EXISTS download_session_files (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    session_id      VARCHAR(36) NOT NULL,

    filename        VARCHAR(255) NOT NULL,
    file_url        TEXT,
    file_type       VARCHAR(20),

    status          VARCHAR(20) NOT NULL,
    skip_reason     VARCHAR(50),

    file_size       BIGINT,
    file_path       VARCHAR(500),
    file_hash       VARCHAR(64),

    queued_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    started_at      DATETIME,
    completed_at    DATETIME,

    worker_id       INT,
    worker_name     VARCHAR(50),

    retry_count     INT DEFAULT 0,
    error_message   TEXT,

    source_metadata JSON,

    FOREIGN KEY (session_id) REFERENCES download_sessions(id) ON DELETE CASCADE,
    INDEX idx_dsf_session (session_id),
    INDEX idx_dsf_status (status),
    INDEX idx_dsf_filename (filename),
    UNIQUE INDEX idx_dsf_session_file (session_id, filename)
);

CREATE TABLE IF NOT EXISTS download_session_events (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    session_id      VARCHAR(36) NOT NULL,

    event_type      VARCHAR(50) NOT NULL,
    event_data      JSON,

    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (session_id) REFERENCES download_sessions(id) ON DELETE CASCADE,
    INDEX idx_dse_session (session_id),
    INDEX idx_dse_type (event_type)
);
```

---

## API Specification

### Download Sessions API

#### Create and Start Download Session

```http
POST /api/v2/downloads/sessions
Content-Type: application/json

{
    "source_type": "rep",
    "fiscal_year": 2569,
    "service_month": 1,
    "scheme": "ucs",
    "max_workers": 3,
    "auto_import": false
}
```

**Response:**
```json
{
    "success": true,
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "message": "Download session created",
    "progress_url": "/api/v2/downloads/sessions/550e8400-e29b-41d4-a716-446655440000/progress"
}
```

#### Get Session Progress

```http
GET /api/v2/downloads/sessions/{session_id}/progress
```

**Response:**
```json
{
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "source_type": "rep",
    "status": "downloading",

    "discovery": {
        "completed": true,
        "total_discovered": 394,
        "already_downloaded": 387,
        "to_download": 7,
        "retry_failed": 0
    },

    "execution": {
        "processed": 390,
        "downloaded": 3,
        "skipped": 387,
        "failed": 0,
        "remaining": 4
    },

    "progress": {
        "percent": 98.98,
        "processed_of_total": "390/394",
        "current_file": "rep_eclaim_10670_20260115_143200.xls",
        "current_worker": "Worker 1 (Chrome/Windows)"
    },

    "timing": {
        "started_at": "2026-01-18T13:39:20Z",
        "updated_at": "2026-01-18T13:42:15Z",
        "elapsed_seconds": 175,
        "eta_seconds": 10
    },

    "workers": [
        {"id": 0, "name": "Chrome/Windows", "status": "downloading", "downloads": 2},
        {"id": 1, "name": "Firefox/Linux", "status": "idle", "downloads": 1},
        {"id": 2, "name": "Safari/Mac", "status": "idle", "downloads": 0}
    ],

    "control": {
        "cancellable": true,
        "resumable": false
    }
}
```

#### Cancel Session

```http
POST /api/v2/downloads/sessions/{session_id}/cancel
Content-Type: application/json

{
    "force": false
}
```

**Response:**
```json
{
    "success": true,
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "cancelled",
    "message": "Download cancelled. 3 files downloaded, 4 remaining.",
    "resumable": true
}
```

#### Resume Session

```http
POST /api/v2/downloads/sessions/{session_id}/resume
```

**Response:**
```json
{
    "success": true,
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "downloading",
    "message": "Download resumed. 4 files remaining.",
    "resume_count": 1
}
```

#### List Sessions (History)

```http
GET /api/v2/downloads/sessions?source_type=rep&limit=20&offset=0
```

**Response:**
```json
{
    "sessions": [
        {
            "session_id": "550e8400-e29b-41d4-a716-446655440000",
            "source_type": "rep",
            "status": "completed",
            "fiscal_year": 2569,
            "service_month": 1,
            "scheme": "ucs",
            "total_discovered": 394,
            "downloaded": 7,
            "skipped": 387,
            "failed": 0,
            "started_at": "2026-01-18T13:39:20Z",
            "completed_at": "2026-01-18T13:43:56Z",
            "duration_seconds": 276
        }
    ],
    "total": 1,
    "limit": 20,
    "offset": 0
}
```

#### Get Session Files

```http
GET /api/v2/downloads/sessions/{session_id}/files?status=failed&limit=50
```

**Response:**
```json
{
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "files": [
        {
            "id": 123,
            "filename": "rep_eclaim_10670_20260115_143200.xls",
            "status": "failed",
            "file_type": "OP",
            "error_message": "Connection timeout",
            "retry_count": 3,
            "worker_name": "Worker 1"
        }
    ],
    "total": 1,
    "filter": {"status": "failed"}
}
```

### SSE Progress Stream

```http
GET /api/v2/downloads/sessions/{session_id}/stream
Accept: text/event-stream
```

**Events:**
```
event: progress
data: {"processed": 390, "downloaded": 3, "skipped": 387, "failed": 0, "percent": 98.98}

event: file.complete
data: {"filename": "rep_eclaim_10670_20260115_143200.xls", "status": "downloaded", "size": 45678}

event: file.skip
data: {"filename": "rep_eclaim_10670_20260115_143201.xls", "reason": "already_exists"}

event: complete
data: {"status": "completed", "downloaded": 7, "skipped": 387, "failed": 0}
```

---

## Implementation Plan

### Phase 1: Core Infrastructure (3-4 days)

1. **Create Database Migration** (`database/migrations/*/012_download_sessions.sql`)
   - download_sessions table
   - download_session_files table
   - download_session_events table

2. **Create Download Manager Core** (`utils/download_manager/`)
   ```
   utils/download_manager/
   +-- __init__.py
   +-- manager.py           # Main DownloadManager class
   +-- session.py           # Session and SessionManager
   +-- progress.py          # ProgressTracker
   +-- events.py            # EventEmitter
   +-- models.py            # Data models (ProgressInfo, FileInfo, etc.)
   +-- exceptions.py        # Custom exceptions
   ```

3. **Create Source Adapter Base** (`utils/download_manager/adapters/`)
   ```
   utils/download_manager/adapters/
   +-- __init__.py
   +-- base.py              # SourceAdapter abstract base class
   +-- rep.py               # REPSourceAdapter
   +-- stm.py               # STMSourceAdapter
   +-- smt.py               # SMTSourceAdapter
   ```

### Phase 2: REP Adapter Implementation (2-3 days)

1. **Migrate REP Download Logic**
   - Extract authentication from `eclaim_downloader_http.py`
   - Implement `REPSourceAdapter.fetch_file_list()`
   - Implement `REPSourceAdapter.download_file()`

2. **Integrate with Download Manager**
   - Wire up session creation
   - Implement progress tracking
   - Add event emission

3. **Update API Endpoints**
   - Add `/api/v2/downloads/sessions` routes
   - Implement SSE stream endpoint

### Phase 3: STM Adapter Implementation (2 days)

1. **Migrate STM Download Logic**
   - Extract from `stm_downloader_http.py`
   - Implement `STMSourceAdapter`

2. **Unify with REP Adapter**
   - Ensure consistent behavior
   - Share common code

### Phase 4: Frontend Integration (2-3 days)

1. **Update Progress Display**
   ```javascript
   // OLD
   const completed = progress.completed || 0;
   progressText.textContent = `${completed}/${total} files`;

   // NEW
   const processed = (progress.downloaded || 0) + (progress.skipped || 0);
   const progressLabel = progress.status === 'discovering'
       ? `Checking files...`
       : `${processed}/${total} files (${progress.downloaded} new, ${progress.skipped} skipped)`;
   progressText.textContent = progressLabel;
   ```

2. **Add Phase Indicators**
   - Discovery phase: "Checking files on server..."
   - Comparison phase: "Found 394 files, 387 already downloaded"
   - Download phase: "Downloading 7 files..."
   - Complete phase: "Done! 7 new files, 0 errors"

3. **Add Cancel/Resume UI**
   - Cancel button during download
   - Resume button for cancelled/failed sessions
   - Session history view

### Phase 5: Migration & Cleanup (1-2 days)

1. **Add Legacy Route Support**
   ```python
   # Keep old routes working
   @app.route('/api/downloads/parallel', methods=['POST'])
   def legacy_parallel_download():
       # Redirect to new system
       return redirect_to_v2_session()
   ```

2. **Migrate Existing History**
   - Import data from `download_history.json` if exists
   - Mark old progress files as deprecated

3. **Deprecation Warnings**
   - Log warnings for old API usage
   - Document migration path

4. **Remove Old Code** (after validation)
   - Remove JSON file-based progress
   - Remove duplicated download logic

---

## Migration Strategy

### Backward Compatibility

1. **Keep Old Endpoints** (v1 routes)
   - `/api/downloads/parallel` -> Creates v2 session internally
   - `/api/downloads/parallel/progress` -> Returns v2 progress in v1 format

2. **Progress Format Translation**
   ```python
   def translate_v2_to_v1_progress(v2_progress):
       return {
           "status": v2_progress.status,
           "total": v2_progress.total_discovered,
           "completed": v2_progress.downloaded,      # v1 only tracked new downloads
           "skipped": v2_progress.skipped,
           "failed": v2_progress.failed,
           "running": v2_progress.status == "downloading",
           # Add new fields for updated frontends
           "processed": v2_progress.processed,
           "progress_percent": v2_progress.progress_percent,
       }
   ```

3. **Gradual Rollout**
   - Week 1: Deploy v2 with backward-compatible v1 routes
   - Week 2: Update frontend to use v2 progress format
   - Week 3: Update frontend to use v2 routes
   - Week 4: Deprecate v1 routes (log warnings)
   - Week 5+: Remove v1 routes

### Data Migration

1. **Export Existing History**
   ```python
   # One-time migration script
   def migrate_download_history():
       # Load from download_history.json
       # Insert into download_sessions with status='migrated'
       # Insert files into download_session_files
   ```

2. **Preserve Progress Files** (during transition)
   - Keep writing to JSON files for old frontends
   - Primary source of truth is database

---

## Error Handling

### Retry Strategy

```python
class RetryConfig:
    max_retries: int = 3
    base_delay: float = 5.0        # seconds
    max_delay: float = 60.0        # seconds
    exponential_base: float = 2.0

    def get_delay(self, attempt: int) -> float:
        delay = self.base_delay * (self.exponential_base ** attempt)
        return min(delay, self.max_delay)
```

### Error Categories

| Category | Action | Retryable | User Notification |
|----------|--------|-----------|-------------------|
| Network Timeout | Retry with backoff | Yes (3x) | After max retries |
| Rate Limited (429) | Pause all workers, backoff | Yes (5x) | Show rate limit warning |
| Auth Error (401/403) | Pause, notify user | No | Immediate |
| Server Error (5xx) | Retry with backoff | Yes (3x) | After max retries |
| File Corruption | Delete and retry | Yes (1x) | After retry fails |
| Disk Full | Pause, notify user | No | Immediate |

### Graceful Degradation

```python
class DownloadManager:
    def handle_worker_failure(self, worker_id: int, error: Exception):
        if self.available_workers > 1:
            # Continue with remaining workers
            self.disable_worker(worker_id)
            self.redistribute_pending_files()
        else:
            # All workers failed - pause session
            self.pause_session("All workers failed")
            self.emit_event(Events.ALL_WORKERS_FAILED)
```

---

## Observability

### Logging

```python
# Structured logging for all download events
logger.info("download.file.complete", extra={
    "session_id": session_id,
    "filename": filename,
    "file_size": file_size,
    "worker_id": worker_id,
    "duration_ms": duration_ms,
})
```

### Metrics

```python
# Key metrics to track
METRICS = {
    # Session metrics
    "downloads.session.created": Counter,
    "downloads.session.completed": Counter,
    "downloads.session.failed": Counter,
    "downloads.session.cancelled": Counter,
    "downloads.session.duration": Histogram,

    # File metrics
    "downloads.file.downloaded": Counter,
    "downloads.file.skipped": Counter,
    "downloads.file.failed": Counter,
    "downloads.file.size": Histogram,
    "downloads.file.duration": Histogram,

    # Worker metrics
    "downloads.worker.active": Gauge,
    "downloads.worker.errors": Counter,
}
```

### Health Checks

```python
@app.route('/api/v2/downloads/health')
def download_health():
    return {
        "status": "healthy",
        "active_sessions": get_active_session_count(),
        "database_connected": check_db_connection(),
        "last_session": get_last_session_info(),
    }
```

---

## Testing Strategy

### Unit Tests

```python
# tests/unit/test_download_manager.py
class TestDownloadManager:
    def test_create_session(self):
        """Session creation stores correct initial state"""

    def test_progress_calculation(self):
        """Progress percent calculated correctly"""

    def test_cancel_session(self):
        """Cancellation marks session and files correctly"""

# tests/unit/test_source_adapters.py
class TestREPAdapter:
    def test_parse_file_list(self):
        """File list parsed correctly from HTML"""

    def test_validate_downloaded_file(self):
        """File validation detects corrupt files"""
```

### Integration Tests

```python
# tests/integration/test_download_flow.py
class TestDownloadFlow:
    def test_full_download_cycle(self):
        """Complete download from discovery to completion"""

    def test_resume_after_cancel(self):
        """Cancelled session resumes correctly"""

    def test_concurrent_sessions(self):
        """Multiple sessions don't interfere"""
```

### Mock NHSO Server

```python
# tests/fixtures/mock_nhso.py
class MockNHSOServer:
    """Flask app that mimics NHSO e-claim responses"""

    def __init__(self, file_count: int = 10, fail_rate: float = 0.1):
        self.file_count = file_count
        self.fail_rate = fail_rate

    @route('/webComponent/validation/ValidationMainAction.do')
    def validation_page(self):
        return render_mock_file_list(self.file_count)

    @route('/webComponent/validation/downloadexcel.do')
    def download_file(self):
        if random.random() < self.fail_rate:
            abort(500)
        return send_mock_excel_file()
```

---

## Concurrent Independent Downloads

### Design Principle: Source Isolation

**Requirement:** REP, STM, and SMT downloads must work independently and concurrently without blocking each other.

```
┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│ REP Session │   │ STM Session │   │ SMT Session │
│  (Running)  │   │  (Running)  │   │ (Queued)    │
└─────────────┘   └─────────────┘   └─────────────┘
      │                  │                  │
      v                  v                  v
┌──────────────────────────────────────────────────┐
│          Download Manager (Thread-safe)          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ REP Pool │  │ STM Pool │  │ SMT Pool │       │
│  └──────────┘  └──────────┘  └──────────┘       │
└──────────────────────────────────────────────────┘
                      │
                      v
┌──────────────────────────────────────────────────┐
│              Database (ACID)                     │
│  Sessions isolated by source_type + session_id   │
└──────────────────────────────────────────────────┘
```

### Session Isolation Strategy

#### 1. Independent Session Management

```python
class DownloadManager:
    def __init__(self):
        # Separate session tracking per source
        self._active_sessions = {
            'rep': None,      # Current REP session
            'stm': None,      # Current STM session
            'smt': None       # Current SMT session
        }
        self._session_locks = {
            'rep': threading.Lock(),
            'stm': threading.Lock(),
            'smt': threading.Lock()
        }

    def can_start_session(self, source_type: str) -> bool:
        """Check if new session can start for this source"""
        with self._session_locks[source_type]:
            active = self._active_sessions[source_type]
            # Allow new session only if no active session for this source
            return active is None or active.is_complete()

    def start_session(self, source_type: str, params: Dict) -> str:
        """Start new download session (concurrent across sources)"""
        if not self.can_start_session(source_type):
            raise SessionConflictError(
                f"A {source_type} download is already running. "
                f"Please wait or cancel the existing session."
            )

        with self._session_locks[source_type]:
            session = self._create_session(source_type, params)
            self._active_sessions[source_type] = session
            return session.session_id
```

#### 2. Resource Pooling Per Source

```python
class DownloadManager:
    def __init__(self):
        # Separate connection pools per source
        self._db_pools = {
            'rep': create_db_pool(pool_size=5),
            'stm': create_db_pool(pool_size=5),
            'smt': create_db_pool(pool_size=3)
        }

        # Separate worker pools per source
        self._executor_pools = {
            'rep': ThreadPoolExecutor(max_workers=3),
            'stm': ThreadPoolExecutor(max_workers=2),
            'smt': ThreadPoolExecutor(max_workers=1)
        }

    def get_resources(self, source_type: str):
        """Get isolated resources for source"""
        return {
            'db_pool': self._db_pools[source_type],
            'executor': self._executor_pools[source_type]
        }
```

#### 3. Concurrency Control

**Database Level:**
```sql
-- Session table already supports concurrent writes with unique constraints
CREATE UNIQUE INDEX idx_session_id ON download_sessions(id);

-- File table prevents duplicate file entries within same session
CREATE UNIQUE INDEX idx_dsf_session_file ON download_session_files(session_id, filename);

-- No cross-source constraints = REP/STM/SMT can write simultaneously
```

**Application Level:**
```python
class SessionManager:
    def update_progress(self, session_id: str, progress: ProgressInfo):
        """Thread-safe progress update"""
        # Use database row-level locking
        with self.db.transaction():
            self.db.execute("""
                UPDATE download_sessions
                SET processed = %s,
                    downloaded = %s,
                    skipped = %s,
                    failed = %s,
                    updated_at = NOW()
                WHERE id = %s
            """, [
                progress.processed,
                progress.downloaded,
                progress.skipped,
                progress.failed,
                session_id
            ])
```

#### 4. UI Multi-Session Display

**API Endpoint:**
```http
GET /api/v2/downloads/active-sessions

Response:
{
    "active_sessions": [
        {
            "session_id": "rep-550e8400",
            "source_type": "rep",
            "status": "downloading",
            "progress": {"percent": 45.5, "processed": 180, "total": 394}
        },
        {
            "session_id": "stm-661f9511",
            "source_type": "stm",
            "status": "downloading",
            "progress": {"percent": 78.2, "processed": 89, "total": 114}
        }
    ],
    "queued_sessions": [
        {
            "session_id": "smt-772g0622",
            "source_type": "smt",
            "status": "queued",
            "message": "Waiting for REP download to complete"
        }
    ]
}
```

**UI Layout:**
```html
<!-- Multiple progress cards, one per active session -->
<div class="download-sessions">
    <!-- REP Session -->
    <div class="session-card" data-source="rep">
        <h4>REP Files (e-Claim)</h4>
        <progress value="180" max="394"></progress>
        <span>180/394 files (45.5%)</span>
        <button class="cancel-btn">Cancel</button>
    </div>

    <!-- STM Session -->
    <div class="session-card" data-source="stm">
        <h4>STM Files (Statement)</h4>
        <progress value="89" max="114"></progress>
        <span>89/114 files (78.2%)</span>
        <button class="cancel-btn">Cancel</button>
    </div>

    <!-- SMT Session (Queued) -->
    <div class="session-card queued" data-source="smt">
        <h4>SMT Data (API)</h4>
        <span>Queued - Will start when ready</span>
    </div>
</div>
```

#### 5. Conflict Prevention

**Rules:**
```python
# Rule 1: Only ONE active session per source at a time
# ✓ Allowed: REP + STM downloading simultaneously
# ✓ Allowed: REP + STM + SMT downloading simultaneously
# ✗ Blocked: REP + REP downloading simultaneously

# Rule 2: New session for same source must wait or cancel existing
if existing_session and existing_session.source_type == new_source_type:
    if existing_session.is_active():
        raise SessionConflictError("Wait or cancel existing session")

# Rule 3: Each source can have multiple completed sessions in history
# ✓ Allowed: Multiple REP sessions in history table
```

#### 6. Performance Considerations

**Resource Limits:**
```python
# Total system limits
MAX_CONCURRENT_SESSIONS = 3      # All sources combined
MAX_WORKERS_PER_SESSION = {
    'rep': 3,    # REP can use up to 3 parallel workers
    'stm': 2,    # STM can use up to 2 parallel workers
    'smt': 1     # SMT uses 1 worker (API calls)
}
MAX_TOTAL_WORKERS = 5            # System-wide worker limit

# Memory limits
MAX_DB_CONNECTIONS = 15          # 5 per source * 3 sources
MAX_CONCURRENT_FILE_WRITES = 10  # Disk I/O limit
```

**Auto-throttling:**
```python
class DownloadManager:
    def check_system_resources(self):
        """Throttle if system is overloaded"""
        cpu_usage = psutil.cpu_percent()
        memory_usage = psutil.virtual_memory().percent
        disk_io = psutil.disk_io_counters().write_bytes

        if cpu_usage > 80 or memory_usage > 85:
            # Reduce workers across all active sessions
            for session in self.get_active_sessions():
                session.reduce_workers(by=1)
```

### Benefits of Independent Concurrent Downloads

1. **No Blocking** - REP download doesn't wait for STM to finish
2. **Better UX** - Users can trigger multiple downloads at once
3. **Resource Efficiency** - Each source uses optimal worker count
4. **Fault Isolation** - REP failure doesn't affect STM/SMT
5. **Flexible Scheduling** - Can schedule REP daily, STM weekly, SMT monthly

### Example Scenarios

**Scenario 1: Start All Downloads at Once**
```bash
# User clicks "Download All" button
# System creates 3 sessions simultaneously:

POST /api/v2/downloads/sessions {"source_type": "rep", ...}  # → session-1
POST /api/v2/downloads/sessions {"source_type": "stm", ...}  # → session-2
POST /api/v2/downloads/sessions {"source_type": "smt", ...}  # → session-3

# All 3 run concurrently:
# - REP: 394 files, 3 workers
# - STM: 114 files, 2 workers
# - SMT: API fetch, 1 worker
```

**Scenario 2: REP Running, User Starts STM**
```bash
# REP already downloading (50% complete)
# User clicks "Download STM"

# System checks: REP ≠ STM → Allowed
POST /api/v2/downloads/sessions {"source_type": "stm", ...}

# Both run simultaneously
# REP continues: 200/394 files
# STM starts: 0/114 files
```

**Scenario 3: REP Running, User Tries Another REP**
```bash
# REP already downloading (50% complete)
# User clicks "Download REP" again

# System checks: REP = REP → Conflict
POST /api/v2/downloads/sessions {"source_type": "rep", ...}

# Response:
{
    "success": false,
    "error": "A REP download session is already running",
    "existing_session_id": "rep-550e8400",
    "options": ["Wait", "Cancel existing and restart"]
}
```

---

## Summary

### Key Benefits of New Design

1. **Accurate Progress** - UI shows `processed/total` instead of `downloaded/total`
2. **Durable State** - Database storage survives restarts
3. **Resumable** - Can continue from where it left off
4. **Observable** - Events, metrics, and structured logging
5. **Testable** - Clean separation of concerns
6. **Extensible** - Easy to add new download sources
7. **Concurrent** - REP, STM, SMT run independently without blocking

### Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `database/migrations/*/012_download_sessions.sql` | Create | New tables |
| `utils/download_manager/__init__.py` | Create | Package init |
| `utils/download_manager/manager.py` | Create | Core manager |
| `utils/download_manager/session.py` | Create | Session handling |
| `utils/download_manager/progress.py` | Create | Progress tracking |
| `utils/download_manager/events.py` | Create | Event system |
| `utils/download_manager/models.py` | Create | Data models |
| `utils/download_manager/adapters/base.py` | Create | Adapter base |
| `utils/download_manager/adapters/rep.py` | Create | REP adapter |
| `utils/download_manager/adapters/stm.py` | Create | STM adapter |
| `routes/downloads_v2.py` | Create | V2 API routes |
| `static/js/app.js` | Modify | Update progress display |
| `app.py` | Modify | Register v2 routes |

### Estimated Timeline

| Phase | Duration | Milestone |
|-------|----------|-----------|
| Phase 1: Core | 3-4 days | Database + Manager working |
| Phase 2: REP | 2-3 days | REP downloads via new system |
| Phase 3: STM | 2 days | STM downloads via new system |
| Phase 4: Frontend | 2-3 days | UI shows accurate progress |
| Phase 5: Migration | 1-2 days | Old code removed |
| **Total** | **10-14 days** | Full migration complete |

---

## Appendix

### A. Current File Structure Reference

```
eclaim-rep-download/
+-- eclaim_downloader_http.py     # REP downloader (to be replaced)
+-- stm_downloader_http.py        # STM downloader (to be replaced)
+-- utils/
|   +-- parallel_downloader.py    # Parallel download (to be replaced)
|   +-- download_history_db.py    # Keep (integrates with new system)
|   +-- log_stream.py             # Keep (used for SSE)
+-- database/
|   +-- migrations/
|       +-- postgresql/
|       |   +-- 005_download_history.sql
|       +-- mysql/
|           +-- 005_download_history.sql
```

### B. Progress JSON Comparison

**Current Format:**
```json
{
  "status": "completed",
  "total": 394,
  "completed": 2,        // Only new downloads
  "skipped": 392,        // Not shown in UI
  "failed": 0,
  "current_files": {},
  "workers": [...]
}
```

**New Format:**
```json
{
  "session_id": "...",
  "status": "completed",
  "discovery": {
    "total_discovered": 394,
    "already_downloaded": 387,
    "to_download": 7
  },
  "execution": {
    "processed": 394,     // Total processed (shown in UI)
    "downloaded": 7,      // New downloads
    "skipped": 387,       // Already existed
    "failed": 0
  },
  "progress": {
    "percent": 100,
    "label": "394/394 files (7 new, 387 skipped)"
  }
}
```

### C. Event Flow Diagram

```
Session Created
      |
      v
+------------------+
| Discovery Phase  |  ---> DISCOVERY_STARTED
+------------------+       DISCOVERY_COMPLETED
      |                    (total: 394, to_download: 7)
      v
+------------------+
| Execution Phase  |
+------------------+
      |
      +----> For each file:
      |         |
      |         +---> Already downloaded? --> FILE_SKIP
      |         |                               |
      |         +---> Download file ----------> FILE_DOWNLOAD_START
      |                   |                     FILE_DOWNLOAD_PROGRESS (optional)
      |                   +---> Success ------> FILE_DOWNLOAD_COMPLETE
      |                   +---> Failure ------> FILE_FAIL
      |                                           |
      |                                           +---> Retry? --> (loop)
      |
      +----> PROGRESS_UPDATE (every N files or N seconds)
      |
      v
+------------------+
| Completion       |  ---> DOWNLOAD_COMPLETE / DOWNLOAD_FAILED / DOWNLOAD_CANCELLED
+------------------+
```
