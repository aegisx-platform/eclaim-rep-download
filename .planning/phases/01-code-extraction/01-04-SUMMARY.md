# 01-04 Summary: Extract STM Downloader

**Status:** COMPLETE
**Date:** 2026-01-12

## Tasks Completed

### Task 1: Extract STMDownloader class
- Created `eclaim_core/downloaders/stm.py` (~300 lines)
- Inherits from BaseDownloader
- **Note:** STM only supports UCS scheme (not multiple schemes as originally planned)
- Features:
  - Fiscal year support (October-September)
  - Person type filtering (IP, OP, All)
  - AJAX endpoint parsing for statement list
  - POST form submission for downloads
  - Retry logic with configurable attempts

### Task 2: Create CLI tool
- Created `cli/download_stm.py` (~170 lines)
- Arguments:
  - `--fiscal-year`: Buddhist Era fiscal year
  - `--month`: Optional month filter (1-12)
  - `--person-type`: IP, OP, or All
  - Standard options: credentials, download-dir, quiet, no-history

## Verification Results

- [x] `from eclaim_core.downloaders import STMDownloader` works
- [x] STMDownloader inherits from BaseDownloader
- [x] `python -m cli.download_stm --help` shows usage
- [x] CLI accepts fiscal-year/month/person-type arguments

## Files Created

```
eclaim_core/downloaders/
├── __init__.py         # Updated exports
└── stm.py              # STMDownloader class

cli/
└── download_stm.py     # CLI tool
```

## Key Implementation Details

| Feature | Implementation |
|---------|----------------|
| Login URL | `/webComponent/login/LoginAction.do` |
| List URL | `/webComponent/ucs/statementUCSAction.do` |
| View URL | `/webComponent/ucs/statementUCSViewAction.do` |
| Download URL | `/webComponent/ucs/statementUCSDownloadAction.do` |
| Method | POST form submission |
| Supported Scheme | **UCS only** |
| Person Types | IP (2), OP (1), All ('') |

## Important Note

**STM only supports UCS scheme.** The original plan assumed multiple schemes (UCS, OFC, SSS, LGO) were supported, but the actual NHSO portal only provides Statement downloads for UCS.

## Next Steps

- Plan 01-05: Extract SMT Fetcher (Budget API - no auth required)
