# STATE.md
## Project State - E-Claim System Separation

---

## Current Position

**Milestone:** 1 - Architecture Separation
**Phase:** 01-code-extraction
**Current Plan:** 01-05 (SMT Fetcher)
**Status:** Plan 01-04 complete, ready for 01-05

---

## Completed Plans

### Phase 01: Code Extraction
- [x] **01-01** Repository Setup & Base Classes (2026-01-12)
  - Created `aegisx-platform/eclaim-downloader-core` GitHub repo
  - Package structure with 8 `__init__.py` files
  - Base classes: BaseDownloader, DownloadResult, DownloadProgress, DownloadLink
  - Enums: DownloadType, FileType, Scheme

- [x] **01-02** Extract Core Utilities (2026-01-12)
  - HistoryManager: Thread-safe JSON history with atomic writes
  - LogStreamer: JSON logging with SSE streaming
  - SettingsManager: Environment + JSON config loading

- [x] **01-03** Extract REP Downloader (2026-01-12)
  - REPDownloader class (~300 lines)
  - CLI tool: `python -m cli.download_rep`
  - Multi-scheme support (8 schemes)
  - File type detection (OP, IP, ORF, IP_APPEAL)

- [x] **01-04** Extract STM Downloader (2026-01-12)
  - STMDownloader class (~300 lines)
  - CLI tool: `python -m cli.download_stm`
  - **UCS only** (not multi-scheme as originally planned)
  - Person type filtering (IP, OP, All)
  - Fiscal year support (October-September)

---

## Accumulated Decisions

1. **Module separation strategy:** Git Submodule (from spec)
   - Pro repo will include core as `lib/eclaim-downloader-core/`
   - Alternative: pip package (deferred)

2. **API versioning:** `/api/v1/` prefix for all endpoints

3. **Package structure:**
   - Core: `eclaim_core/{downloaders,auth,history,logging,config,api}`
   - Pro: `eclaim_pro/{importers,scheduler,reconciliation,api}`

4. **Dependencies:**
   - Removed `humanize` dependency from core (internal implementation)
   - Core requires: requests, beautifulsoup4, lxml

5. **HTML Parser:** Using `lxml` for BeautifulSoup (faster than html.parser)

6. **STM Scheme Support:** UCS only (NHSO limitation, not multi-scheme)

---

## Deferred Issues

None yet.

---

## Blockers/Concerns

1. ~~**GitHub repo creation:** ต้องสร้าง `eclaim-downloader-core` repo ใหม่บน GitHub~~ RESOLVED
2. **Import path changes:** ต้อง update imports ทั้ง codebase หลัง integration

---

## Brief Alignment

- **Spec approved:** `SYSTEM_REDESIGN_SPEC.md` created and reviewed
- **Codebase mapped:** `.planning/codebase/` contains analysis
- **Roadmap defined:** 4 phases identified
- **Core repo created:** `aegisx-platform/eclaim-downloader-core`
- **Core utilities extracted:** HistoryManager, LogStreamer, SettingsManager
- **REP Downloader extracted:** REPDownloader + CLI tool
- **STM Downloader extracted:** STMDownloader + CLI tool (UCS only)

---

## Next Action

```
/gsd:execute-plan 01-05
```

Execute Plan 01-05: Extract SMT Fetcher (Budget API) + Finalize Phase 1
