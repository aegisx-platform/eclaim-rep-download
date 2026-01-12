# ROADMAP.md
## E-Claim System Separation - Migration Roadmap

---

## Milestone 1: Architecture Separation

**Goal:** แยก monolithic codebase ออกเป็น 2 repos (FREE core + PAID pro)

---

## Phase 1: Code Extraction
**Directory:** `.planning/phases/01-code-extraction/`
**Status:** Not Started
**Research:** No (ใช้ patterns ที่มีอยู่)

### Objective
สร้าง `eclaim-downloader-core` repo ใหม่และ extract download components ออกมา

### Deliverables
1. New repo structure: `eclaim-downloader-core/`
2. Package structure: `eclaim_core/{downloaders,auth,history,logging,config}`
3. Abstract base classes: `BaseDownloader`, `DownloadResult`, `DownloadProgress`
4. Enums: `Scheme`, `FileType`, `DownloadType`
5. CLI tools: `cli/download_rep.py`, `cli/download_stm.py`, `cli/fetch_smt.py`

### Key Files to Extract
- `eclaim_downloader_http.py` → `eclaim_core/downloaders/rep.py`
- `stm_downloader_http.py` → `eclaim_core/downloaders/stm.py`
- `smt_budget_fetcher.py` → `eclaim_core/downloaders/smt.py`
- `utils/history_manager.py` → `eclaim_core/history/manager.py`
- `utils/log_stream.py` → `eclaim_core/logging/streamer.py`
- `utils/settings_manager.py` → `eclaim_core/config/settings.py`

### Dependencies
- None (first phase)

---

## Phase 2: API Development
**Directory:** `.planning/phases/02-api-development/`
**Status:** Not Started
**Research:** No

### Objective
สร้าง REST API สำหรับ core module (Flask Blueprint)

### Deliverables
1. Flask Blueprint: `eclaim_core/api/`
2. API Routes:
   - `POST /api/v1/download/rep` - Download REP files
   - `POST /api/v1/download/stm` - Download STM files
   - `POST /api/v1/download/smt` - Fetch SMT budget
   - `GET /api/v1/download/status` - Download status
   - `GET /api/v1/history` - Download history
   - `GET /api/v1/files` - List files
   - `GET /api/v1/logs/stream` - SSE log streaming
3. Request/Response schemas (Pydantic or Marshmallow)
4. Minimal web app: `web/app.py`
5. Tests: `tests/test_downloaders.py`, `tests/test_api.py`

### Dependencies
- Phase 1 (core module must exist)

---

## Phase 3: Pro Integration
**Directory:** `.planning/phases/03-pro-integration/`
**Status:** Not Started
**Research:** No

### Objective
Integrate core module เข้ากับ pro repo (repo นี้) ผ่าน git submodule

### Deliverables
1. Add core as submodule: `lib/eclaim-downloader-core/`
2. Update imports ทั้ง codebase:
   - `from eclaim_downloader_http import` → `from lib.core.eclaim_core.downloaders import`
3. Refactor `app.py` to use core blueprint
4. Create pro-only package: `eclaim_pro/{importers,scheduler,reconciliation,api}`
5. Pro API endpoints: `/api/v1/pro/*`

### Dependencies
- Phase 1 (core exists)
- Phase 2 (core API exists)

---

## Phase 4: Testing & Documentation
**Directory:** `.planning/phases/04-testing-docs/`
**Status:** Not Started
**Research:** No

### Objective
ทดสอบทั้ง 2 repos และเขียน documentation

### Deliverables
1. **Testing:**
   - Core module works standalone (FREE version)
   - Core module works as submodule (PRO version)
   - All 3 download types functional
   - History tracking correct
   - API endpoints respond correctly
   - SSE log streaming works
   - PRO import still works
   - PRO scheduler still works
   - Docker builds work

2. **Documentation:**
   - README.md for core repo
   - API documentation (OpenAPI/Swagger)
   - Installation guide
   - Usage examples
   - Migration guide for existing users

### Dependencies
- Phase 1, 2, 3 (all complete)

---

## Domain Expertise

- `.planning/codebase/ARCHITECTURE.md` - System architecture
- `.planning/codebase/STACK.md` - Technology stack
- `.planning/codebase/CONVENTIONS.md` - Code conventions
- `.planning/codebase/INTEGRATIONS.md` - External integrations

---

## Notes

- **Strategy:** Git Submodule (recommended in spec)
- **Licensing:** Core = MIT/Apache 2.0, Pro = Commercial
- **Detailed Spec:** `SYSTEM_REDESIGN_SPEC.md`
